"""LLM wrapper for CVButler using Ollama."""

import json
import httpx
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Response from LLM inference."""
    success: bool
    content: str
    model: str
    error: Optional[str] = None


class OllamaClient:
    """Client for local Ollama API."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral:7b"):
        self.base_url = base_url
        self.model = model
        # Increased from 60 to 300 seconds
        self.client = httpx.Client(timeout=300.0)

    def check_availability(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name") for m in models]
                return self.model in model_names or self.model.split(':')[0] in model_names
            return False
        except Exception:
            return False

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate response using Ollama."""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            payload.update(kwargs)

            response = self.client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                return LLMResponse(
                    success=True,
                    content=result.get("response", ""),
                    model=self.model
                )
            else:
                return LLMResponse(
                    success=False,
                    content="",
                    model=self.model,
                    error=f"Ollama API error: {response.status_code}"
                )
        except Exception as e:
            return LLMResponse(
                success=False,
                content="",
                model=self.model,
                error=f"Ollama connection error: {str(e)}"
            )


class LLMManager:
    """Manager for Ollama LLM provider."""

    def __init__(self):
        self.ollama = OllamaClient()

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate response using Ollama."""
        response = self.ollama.generate(prompt, **kwargs)
        return response

    def analyze_candidate(self, job_desc: str, resume_text: str) -> Dict[str, Any]:
        """Analyze candidate using keyword matching without LLM."""
        import re

        # Extract keywords from job description
        # words >= 4 chars
        job_words = set(re.findall(r'\b\w{4,}\b', job_desc.lower()))
        # Remove common stopwords (simple list)
        stopwords = {'the', 'and', 'are', 'but', 'for', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'had', 'by', 'hot', 'but', 'some', 'very', 'from', 'they', 'know', 'want', 'been', 'good', 'their', 'said', 'each', 'which', 'she', 'any', 'that', 'set', 'may', 'old', 'such', 'way', 'after', 'take', 'how', 'then', 'will', 'were', 'see', 'more', 'two', 'use', 'has', 'too', 'your', 'has', 'him', 'its',
                     'his', 'who', 'did', 'way', 'get', 'just', 'let', 'with', 'into', 'than', 'out', 'when', 'look', 'most', 'this', 'will', 'would', 'have', 'there', 'what', 'were', 'what', 'said', 'only', 'come', 'many', 'could', 'here', 'come', 'over', 'then', 'think', 'them', 'said', 'come', 'about', 'like', 'well', 'should', 'want', 'an', 'have', 'here', 'work', 'year', 'where', 'you', 'must', 'they', 'first', 'years'}
        job_keywords = job_words - stopwords

        # Extract words from resume
        resume_words = set(re.findall(r'\b\w{4,}\b', resume_text.lower()))
        resume_words = resume_words - stopwords

        # Find matching keywords
        matching_keywords = job_keywords & resume_words

        # Calculate score (Jaccard similarity)
        if not job_keywords:
            score = 0.0
        else:
            score = len(matching_keywords) / len(job_keywords)

        # Ensure score is between 0 and 1
        score = min(1.0, max(0.0, score))

        # Create explanation
        explanation = f"Keyword matching analysis found {len(matching_keywords)} out of {len(job_keywords)} job keywords present in the resume."

        # Citations are the matching keywords
        citations = list(matching_keywords)[:5]  # Limit to 5

        return {
            "score": score,
            "explanation": explanation,
            "citations": citations
        }

    def _parse_marker_response(self, content: str) -> Dict[str, Any]:
        """Parse text-based marker response from LLM."""
        score = 0.0
        explanation = "Analysis completed"
        citations = []

        # Extract score (look for patterns like "Score: 0.75")
        import re
        score_match = re.search(
            r'score[:\s]*([-+]?\d*\.?\d+)', content, re.IGNORECASE)
        if score_match:
            try:
                score = float(score_match.group(1))
                score = min(1.0, max(0.0, score))  # Ensure 0-1 range
            except (ValueError, IndexError):
                score = 0.0

        # Extract explanation
        expl_match = re.search(
            r'explanation[:\s]*(.+)', content, re.IGNORECASE | re.DOTALL)
        if expl_match:
            explanation = expl_match.group(1).strip()
        else:
            # If no clear explanation marker, use first non-empty lines
            lines = [line.strip()
                     for line in content.split('\n') if line.strip()]
            # Avoid number lines
            if lines and not any(char.isdigit() for char in lines[0][:10]):
                explanation = lines[0][:200]  # First 200 chars

        # Extract citations
        citation_match = re.search(
            r'citations?[:\s]*(.+)', content, re.IGNORECASE | re.DOTALL)
        if citation_match:
            citations_text = citation_match.group(1).strip()
            # Split by common delimiters
            citations = [c.strip() for c in re.split(
                r'[;,\n]', citations_text) if c.strip()]
            citations = citations[:5]  # Limit to 5 citations

        return {
            "score": score,
            "explanation": explanation or "Analysis completed successfully",
            "citations": citations
        }
