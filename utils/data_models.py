"""Data models for CVButler."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class Language(str, Enum):
    EN = "en"
    NL = "nl"
    DE = "de"
    FR = "fr"


class JobDescription(BaseModel):
    """Job description data model."""
    id: str
    text: str
    language: Language = Language.EN
    upload_timestamp: datetime
    filename: str
    anonymized_text: Optional[str] = None
    tags: Optional[List[str]] = []


class Resume(BaseModel):
    """Resume data model."""
    id: str
    original_filename: str
    extracted_text: str
    anonymized_text: Optional[str] = None
    language: Language = Language.EN
    upload_timestamp: datetime
    tags: Optional[List[str]] = []


class CandidateRanking(BaseModel):
    """Candidate ranking data model."""
    id: str
    job_id: str
    resume_id: str
    score: float  # 0-1 score
    explanation: str
    citations: List[Dict[str, Any]]  # References to specific text matches
    created_at: datetime
    model_used: str  # Which LLM model was used


# Prompt templates
class PromptTemplates:
    """Prompt templates for different LLM tasks with best prompt engineering practices."""

    @staticmethod
    def anonymize_resume(resume_text: str) -> str:
        """Prompt for anonymizing candidate resume by removing all PII and bias-prone information."""
        return f"""You are an AI assistant skilled in anonymizing resumes for unbiased recruitment.

Your task is to carefully remove or redact all personally identifiable information (PII) and any data points that could lead to bias, including but not limited to:
- Full names and initials
- Addresses and locations
- Phone numbers and emails
- Photos or references to images
- Gender, age, ethnicity, marital status, or any demographic info
- Other identifying references

Please return the redacted resume text with placeholders like [REDACTED] in place of removed information.

Resume text:
{resume_text}
"""

    @staticmethod
    def extract_resume_info(anonymized_resume_text: str) -> str:
        """Prompt for extracting structured, unbiased information from anonymized CV."""
        return f"""Extract the following from the anonymized resume text, focusing only on professional qualifications and experience:
- Roles and responsibilities in previous jobs
- Technical skills and competencies
- Education, certifications, and training
- Key achievements, projects, and measurable results

Anonymized Resume:
{anonymized_resume_text}

Provide a clear, structured summary of the candidate's qualifications without referencing any personal details.
"""

    @staticmethod
    def rank_candidate(job_desc: str, resume_text: str) -> str:
        """Prompt for ranking a candidate against a job description."""
        return f"""You are evaluating a candidate's suitability for a job.

Job Description:
{job_desc}

Candidate Resume:
{resume_text}

IMPORTANT: Respond ONLY with valid JSON in this exact format. No other text.

{{
  "score": 0.85,
  "explanation": "Brief 2-3 sentence explanation of fit quality",
  "citations": ["specific skill match", "another match"]
}}

The score must be between 0.0 and 1.0 where 1.0 is perfect match."""

    @staticmethod
    def generate_explanation(job_desc: str, extracted_resume_info: str, score: float) -> str:
        """Prompt for generating a detailed explanation of ranking with citations."""
        return f"""Provide an in-depth explanation for why the candidate received a score of {score}/1.0 for this job.

Use the following information:

Job Description:
{job_desc}

Candidate Profile Summary:
{extracted_resume_info}

Highlight:
- Candidate's strengths and key fit factors
- Areas where candidate may be lacking or less aligned
- Specific examples or citations from both texts supporting these insights
- The overall rationale behind the ranking score
"""


# JSON file structures
class DataStore:
    """Manages persistence to JSON files."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist."""
        import os
        os.makedirs(self.data_dir, exist_ok=True)

    def save_jobs(self, jobs: List[JobDescription]):
        """Save job descriptions to JSON."""
        import json
        data = [job.dict() for job in jobs]
        with open(f"{self.data_dir}/jobs.json", 'w') as f:
            json.dump(data, f, default=str, indent=2)

    def save_resumes(self, resumes: List[Resume]):
        """Save resumes to JSON."""
        import json
        data = [resume.dict() for resume in resumes]
        with open(f"{self.data_dir}/resumes.json", 'w') as f:
            json.dump(data, f, default=str, indent=2)

    def save_rankings(self, job_id: str, rankings: List[CandidateRanking]):
        """Save candidate rankings to JSON."""
        import json
        data = [ranking.dict() for ranking in rankings]
        with open(f"{self.data_dir}/rankings_{job_id}.json", 'w') as f:
            json.dump(data, f, default=str, indent=2)

    def load_jobs(self) -> List[JobDescription]:
        """Load job descriptions from JSON."""
        import json
        import os
        try:
            if os.path.exists(f"{self.data_dir}/jobs.json"):
                with open(f"{self.data_dir}/jobs.json", 'r') as f:
                    data = json.load(f)
                    return [JobDescription(**item) for item in data]
            return []
        except Exception as e:
            print(f"Error loading jobs: {e}")
            return []

    def load_resumes(self) -> List[Resume]:
        """Load resumes from JSON."""
        import json
        import os
        try:
            if os.path.exists(f"{self.data_dir}/resumes.json"):
                with open(f"{self.data_dir}/resumes.json", 'r') as f:
                    data = json.load(f)
                    return [Resume(**item) for item in data]
            return []
        except Exception as e:
            print(f"Error loading resumes: {e}")
            return []

    def load_rankings(self, job_id: str) -> List[CandidateRanking]:
        """Load candidate rankings from JSON."""
        import json
        import os
        try:
            ranking_file = f"{self.data_dir}/rankings_{job_id}.json"
            if os.path.exists(ranking_file):
                with open(ranking_file, 'r') as f:
                    data = json.load(f)
                    return [CandidateRanking(**item) for item in data]
            return []
        except Exception as e:
            print(f"Error loading rankings: {e}")
            return []
