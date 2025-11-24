"""Text extraction utilities for CVButler."""

import os
import re
from pathlib import Path
from typing import Optional
from html.parser import HTMLParser

from PyPDF2 import PdfReader
from docx import Document


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file."""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text.strip()
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return ""


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from Word document."""
    try:
        doc = Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error extracting DOCX: {e}")
        return ""


def extract_text_from_file(file_path: str) -> str:
    """Extract text based on file extension."""
    path = Path(file_path)
    if path.suffix.lower() == '.pdf':
        return extract_text_from_pdf(file_path)
    elif path.suffix.lower() in ['.docx', '.doc']:
        return extract_text_from_docx(file_path)
    elif path.suffix.lower() == '.html':
        return extract_text_from_html(file_path)
    else:
        # Try to read as plain text
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return ""


def extract_text_from_html(file_path: str) -> str:
    """Extract text from HTML file using regex."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        # Remove HTML tags using regex
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        # Remove extra whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text)
        return clean_text.strip()
    except Exception as e:
        print(f"Error extracting HTML: {e}")
        return ""


def detect_language(text: str) -> str:
    """Simple language detection (placeholder)."""
    # TODO: Implement proper language detection
    # For now, assume English
    return "en"
