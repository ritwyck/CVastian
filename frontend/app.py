"""Streamlit frontend for CVButler."""

import streamlit as st
import requests
import json
from pathlib import Path
from typing import List, Dict, Any
import time
import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Configuration
BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="CVButler", page_icon="📄", layout="wide")


def check_backend_status():
    """Check if backend is available."""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return response.status_code == 200, response.json()
    except Exception as e:
        return False, {"error": str(e)}


def upload_job_description(file=None, text=None):
    """Upload job description to backend."""
    if file is not None:
        files = {"file": (file.name, file.getvalue(), file.type)}
        response = requests.post(f"{BACKEND_URL}/api/jobs/upload", files=files)
    elif text:
        data = {"text": text}
        response = requests.post(f"{BACKEND_URL}/api/jobs/upload", data=data)
    else:
        return None

    return response.json() if response.status_code == 200 else None


def upload_resumes(files):
    """Upload resumes to backend."""
    if not files:
        return None

    file_data = []
    for file in files:
        file_data.append(("files", (file.name, file.getvalue(), file.type)))

    response = requests.post(
        f"{BACKEND_URL}/api/resumes/upload", files=file_data)
    return response.json() if response.status_code == 200 else None


def analyze_candidates(job_id):
    """Run candidate analysis."""
    response = requests.post(f"{BACKEND_URL}/api/analyze/{job_id}")
    return response.json() if response.status_code == 200 else None


def get_jobs():
    """Get list of uploaded jobs."""
    response = requests.get(f"{BACKEND_URL}/api/jobs")
    return response.json() if response.status_code == 200 else []


def get_results(job_id):
    """Get analysis results for a job."""
    response = requests.get(f"{BACKEND_URL}/api/results/{job_id}")
    return response.json() if response.status_code == 200 else None


def main():
    st.title("🚀 CVButler - AI-Powered ATS")
    st.markdown(
        """
        Upload job descriptions and candidate resumes to get AI-powered rankings
        with detailed explanations and citations.
        """
    )

    # Check backend status
    backend_ok, backend_info = check_backend_status()
    if not backend_ok:
        st.error("❌ Backend is not running. Please start the backend first.")
        st.code("cd backend && python main.py")
        st.stop()

    # Show backend status
    status_col, model_col = st.columns(2)
    with status_col:
        status_color = "🟢" if backend_ok else "🔴"
        st.success(f"{status_color} Backend Connected")

    with model_col:
        if backend_info:
            preferred = backend_info.get("preferred_provider", "unknown")
            ollama_status = backend_info.get(
                "llm_providers", {}).get("ollama", "unknown")
            openai_status = backend_info.get(
                "llm_providers", {}).get("openai", "unknown")

            if preferred == "ollama":
                st.info(f"🧠 Using Ollama ({ollama_status})")
            elif preferred == "openai":
                st.info(f"🧠 Using OpenAI ({openai_status})")
            else:
                st.warning("⚠️ No LLM provider configured")

    # Main interface
    tab1, tab3 = st.tabs(["📝 New Analysis", "ℹ️ Help"])

    with tab1:
        st.header("Upload Job Description & Resumes")

        # Job Description Section
        st.subheader("1. Job Description")
        job_col1, job_col2 = st.columns([1, 1])

        with job_col1:
            job_file = st.file_uploader(
                "Upload job description file",
                type=["pdf", "docx", "txt", "html"],
                key="job_file"
            )

        with job_col2:
            job_text = st.text_area(
                "Or paste job description text",
                height=150,
                key="job_text"
            )

        # Resume Section
        st.subheader("2. Candidate Resumes")
        resume_files = st.file_uploader(
            "Upload candidate resumes",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            key="resume_files"
        )

        # Analysis Button
        if st.button("🚀 Start Analysis", type="primary", use_container_width=True):
            # Validation
            if not job_file and not job_text.strip():
                st.error("Please provide a job description (file or text)")
                st.stop()

            if not resume_files:
                st.error("Please upload at least one resume")
                st.stop()

            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # Step 1: Upload job description
                status_text.text("Uploading job description...")
                job_result = upload_job_description(
                    job_file, job_text if job_text.strip() else None)
                if not job_result:
                    st.error("Failed to upload job description")
                    st.stop()
                job_id = job_result["job_id"]
                progress_bar.progress(25)

                # Step 2: Upload resumes
                status_text.text("Processing resumes...")
                resume_result = upload_resumes(resume_files)
                if not resume_result:
                    st.error("Failed to upload resumes")
                    st.stop()
                progress_bar.progress(50)

                # Step 3: Run analysis
                status_text.text("Running AI analysis...")
                analysis_result = analyze_candidates(job_id)
                if not analysis_result:
                    st.error("Analysis failed")
                    st.stop()
                progress_bar.progress(100)

                # Success
                status_text.text("Analysis complete!")
                st.success(f"✅ Analysis complete! Job ID: {job_id}")

                # Show results
                st.header("📊 Results")
                rankings = analysis_result.get("rankings", [])

                for i, ranking in enumerate(rankings[:3]):  # Show top 3
                    with st.expander(f"🏆 Rank #{i+1}: {ranking['filename']} (Score: {ranking['score']:.2f})"):
                        st.write(ranking['explanation'])

                        # Citations
                        if ranking.get('citations'):
                            st.subheader("📌 Key Citations")
                            # Top 3 citations
                            for citation in ranking['citations'][:3]:
                                st.write(f"- {citation}")

            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")
            finally:
                progress_bar.empty()
                status_text.empty()

    with tab3:
        st.header("How to Use CVButler")

        st.markdown("""
        ## Quick Start

        1. **Upload Job Description**: Provide a job description via file upload or text input
        2. **Upload Resumes**: Upload multiple candidate resumes (PDF, DOCX, or TXT)
        3. **Run Analysis**: Click "Start Analysis" to get AI-powered rankings
        4. **View Results**: Check detailed rankings with explanations and citations

        ## Features

        - 🤖 **AI-Powered Matching**: Uses local LLMs (Ollama) with OpenAI fallback
        - 🛡️ **Privacy-Focused**: Anonymizes PII and bias indicators before analysis
        - 📊 **Detailed Explanations**: Provides ranking rationale with text citations
        - 💾 **Persistent Storage**: Results saved for future reference

        ## Technical Details

        - **Backend**: FastAPI with text extraction and LLM integration
        - **Frontend**: Streamlit for intuitive file uploads and result visualization
        - **LLM Support**: Ollama (Qwen, Mistral, Llama2) - OpenAI removed for simplicity
        - **Data Storage**: JSON-based session-specific storage

        ## Setup Requirements

        - **Backend**: Install Ollama and pull a model (`ollama pull qwen:4b`)
        - **Dependencies**: `pip install -r requirements.txt`
        - **Running**: Start backend first, then streamlit app
        """)


if __name__ == "__main__":
    main()
