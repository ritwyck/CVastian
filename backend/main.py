"""FastAPI backend for CVButler."""

from fastapi.responses import JSONResponse
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import shutil
import tempfile
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from utils.data_models import DataStore, JobDescription, Resume, CandidateRanking, Language
from utils.text_extraction import extract_text_from_file
from utils.anonymization import anonymize_text
from utils.llm_wrapper import LLMManager
import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)


app = FastAPI(title="CVButler Backend", version="1.0.0")

# Add CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
data_store = DataStore()
llm_manager = LLMManager()

# Temporary storage for uploaded files
UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "CVButler backend is running"}


@app.get("/health")
async def health():
    """Detailed health check."""

    return {
        "status": "healthy",
        "analysis_method": "keyword_matching",
        "description": "Analysis performed using keyword matching without LLM"
    }


@app.post("/api/jobs/upload")
async def upload_job_description(
    file: UploadFile = File(...),
    text: Optional[str] = Form(None)
) -> JSONResponse:
    """Upload a job description file or provide text directly."""
    try:
        job_id = str(uuid.uuid4())

        if file.filename:
            # Save uploaded file temporarily
            file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Extract text
            extracted_text = extract_text_from_file(str(file_path))

            # Clean up temp file
            file_path.unlink(missing_ok=True)

        elif text:
            extracted_text = text
        else:
            raise HTTPException(
                status_code=400, detail="Either file or text must be provided")

        # Anonymize text
        anonymized_text, audit = anonymize_text(extracted_text)

        # Create job description
        job = JobDescription(
            id=job_id,
            text=extracted_text,
            language=Language.EN,  # TODO: Detect language
            upload_timestamp=datetime.now(),
            filename=file.filename if file.filename else "text_input.txt",
            anonymized_text=anonymized_text
        )

        # Clear all previous data for fresh session
        data_store.save_jobs([job])
        data_store.save_resumes([])

        return JSONResponse(content={
            "job_id": job_id,
            "text_length": len(extracted_text),
            "candidates_count": 0,  # Will be updated when analyzed
            "anonymized": True,
            "upload_timestamp": job.upload_timestamp.isoformat()
        })

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process job description: {str(e)}")


@app.post("/api/resumes/upload")
async def upload_resumes(files: List[UploadFile] = File(...)) -> JSONResponse:
    """Upload multiple resume files."""
    try:
        processed_resumes = []

        # Clear previous resumes and rankings for fresh session
        data_store.save_resumes([])

        for file in files:
            resume_id = str(uuid.uuid4())

            # Save uploaded file temporarily
            file_path = UPLOAD_DIR / f"{resume_id}_{file.filename}"
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Extract text
            extracted_text = extract_text_from_file(str(file_path))

            # Anonymize text
            anonymized_text, audit = anonymize_text(extracted_text)

            # Create resume
            resume = Resume(
                id=resume_id,
                original_filename=file.filename,
                extracted_text=extracted_text,
                anonymized_text=anonymized_text,
                language=Language.EN,  # TODO: Detect language
                upload_timestamp=datetime.now()
            )

            # Add to current resumes
            processed_resumes.append({
                "resume_id": resume_id,
                "filename": file.filename,
                "text_length": len(extracted_text),
                "anonymized": True,
                "upload_timestamp": resume.upload_timestamp.isoformat()
            })

            # Clean up temp file
            file_path.unlink(missing_ok=True)

        # Save current resumes
        current_resumes = []
        for pr in processed_resumes:
            resume = Resume(
                id=pr["resume_id"],
                original_filename=pr["filename"],
                extracted_text="",  # We don't need to save this again
                anonymized_text="",
                language=Language.EN,
                upload_timestamp=datetime.fromisoformat(pr["upload_timestamp"])
            )
            current_resumes.append(resume)

        data_store.save_resumes(current_resumes)

        return JSONResponse(content={
            "message": f"Successfully processed {len(processed_resumes)} resumes",
            "resumes": processed_resumes
        })

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process resumes: {str(e)}")


@app.post("/api/analyze/{job_id}")
async def analyze_candidates(job_id: str) -> JSONResponse:
    """Analyze all uploaded resumes against the specified job."""
    try:
        # Load job
        jobs = data_store.load_jobs()
        job = next((j for j in jobs if j.id == job_id), None)
        if not job:
            raise HTTPException(
                status_code=404, detail="Job description not found")

        # Load resumes
        resumes = data_store.load_resumes()
        if not resumes:
            raise HTTPException(
                status_code=400, detail="No resumes uploaded yet")

        # Load existing rankings for this job (if any)
        existing_rankings = data_store.load_rankings(job_id)

        # Analyze each resume
        rankings = []
        for resume in resumes:
            # Skip if already analyzed
            if any(r.resume_id == resume.id for r in existing_rankings):
                existing = next(
                    r for r in existing_rankings if r.resume_id == resume.id)
                rankings.append({
                    "resume_id": resume.id,
                    "filename": resume.original_filename,
                    "score": existing.score,
                    "explanation": existing.explanation,
                    "citations": existing.citations
                })
                continue

            print(f"Analyzing {resume.original_filename}...")

            # Use LLM to analyze
            analysis = llm_manager.analyze_candidate(
                job.anonymized_text or job.text,
                resume.anonymized_text or resume.extracted_text
            )

            # Create ranking
            ranking = CandidateRanking(
                id=str(uuid.uuid4()),
                job_id=job_id,
                resume_id=resume.id,
                score=analysis["score"],
                explanation=analysis["explanation"],
                citations=analysis["citations"],
                created_at=datetime.now(),
                model_used="keyword-matching"
            )

            existing_rankings.append(ranking)

            rankings.append({
                "resume_id": resume.id,
                "filename": resume.original_filename,
                "score": ranking.score,
                "explanation": ranking.explanation,
                "citations": ranking.citations
            })

        # Save all rankings
        data_store.save_rankings(job_id, existing_rankings)

        # Sort by score (highest first)
        rankings.sort(key=lambda x: x["score"], reverse=True)

        return JSONResponse(content={
            "job_id": job_id,
            "total_candidates": len(rankings),
            "rankings": rankings[:10],  # Return top 10
            "analysis_timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        print(f"Analysis error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze candidates: {str(e)}")


@app.get("/api/jobs")
async def list_jobs():
    """List all uploaded job descriptions."""
    jobs = data_store.load_jobs()
    return [
        {
            "job_id": job.id,
            "filename": job.filename,
            "upload_timestamp": job.upload_timestamp.isoformat(),
            "candidates_count": len(data_store.load_rankings(job.id))
        }
        for job in jobs
    ]


@app.get("/api/results/{job_id}")
async def get_results(job_id: str, limit: int = 10):
    """Get ranking results for a job."""
    jobs = data_store.load_jobs()
    job = next((j for j in jobs if j.id == job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    rankings = data_store.load_rankings(job_id)
    resumes = data_store.load_resumes()

    # Create response with resume details
    results = []
    for ranking in rankings:
        resume = next((r for r in resumes if r.id == ranking.resume_id), None)
        if resume:
            results.append({
                "rank": len([r for r in rankings if r.score > ranking.score]) + 1,
                "resume_id": ranking.resume_id,
                "filename": resume.original_filename,
                "score": ranking.score,
                "explanation": ranking.explanation,
                "citations": ranking.citations,
                "model_used": ranking.model_used,
                "analyzed_at": ranking.created_at.isoformat()
            })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"job_id": job_id, "results": results[:limit]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
