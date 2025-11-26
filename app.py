import streamlit as st
from pathlib import Path
from docx import Document
import pypandoc
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from tqdm import tqdm
import pdfplumber
import re
import tempfile
from fpdf import FPDF
import datetime
import io
import google.generativeai as genai
from dotenv import load_dotenv

import os
import sys

if os.environ.get('ENVIRONMENT') == 'production':

    st.set_option('server.headless', True)
    st.set_option('server.port', int(os.environ.get('PORT', 8501)))
    st.set_option('server.address', '0.0.0.0')

load_dotenv()

#! gemma3 model is being used here, the best that my hardware could support.
#! attempted using larger models but ran into issues.
#! the solution was inspired from:
#! • https://www.youtube.com/watch?v=bp2eev21Qfo - this was to understand how models are set up locally and called via API.
#! • https://www.youtube.com/watch?v=EECUXqFrwbc&list=WL&index=2 - this was to understand how to structure the solution.
#! naturally a cloud based gemini api integrated solution would be faster and more powerful, but a local system provides more security.
#! loading sbert model for similarity scoring. plan to use this to add some quantitatively support the decision making of the llm.


#! model configuration for better responses.
model_config = {
    "temperature": 0.2,
    "repeat_penalty": 1.15
}

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_configured = False

if GOOGLE_API_KEY and GOOGLE_API_KEY != "YOUR_API_KEY":
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content("Hello")
        gemini_configured = True
    except Exception as e:
        st.error(f"Error configuring Gemini API: {e}")
        gemini_configured = False
else:
    st.warning("GOOGLE_API_KEY not found or not set properly. Please check your .env file.")

def call_ollama(prompt, model="gemma3:4b"):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": model_config
    }
    resp = requests.post("http://localhost:11434/api/generate", json=payload)
    return resp.json().get("response", "")

def call_gemini(prompt):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Error calling Gemini API: {e}")
        return ""

#! adding a pre-procesing step to make job description more concise. this should make the analysis faster by making the prompt smaller.
#! decided against pre-processing resumes as they are generally concise already.
#! if the pre-processing step negatively affects a candidate's evaluation, then that would be unfair.
#! pre-processing job description would impact all candidates equally.

def preprocess_job_text(text):
    text = ' '.join(text.split())
    sentences = text.split('. ')
    filtered_sentences = []

    filler_words = [
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "with", "by", "from", "of", "as", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "can", "this",
        "that", "these", "those", "just", "only", "really", "very", "quite",
        "also", "then", "now", "well", "so", "however", "therefore",
        "furthermore", "moreover", "nevertheless", "nonetheless", "thus",
        "hence", "accordingly", "consequently", "meanwhile", "otherwise",
        "besides", "anyway", "anyhow", "incidentally", "naturally", "certainly",
        "definitely", "probably", "possibly", "perhaps", "maybe", "generally",
        "usually", "typically", "normally", "commonly", "regularly", "sometimes",
        "occasionally", "often", "frequently", "rarely", "seldom", "hardly",
        "scarcely", "barely", "almost", "nearly", "approximately", "roughly",
        "about", "around", "like", "such", "etc", "etcetera", "including",
        "along", "among", "upon", "within", "without", "toward", "towards",
        "against", "during", "since", "until", "after", "before", "because",
        "though", "although", "while", "whereas", "whether", "if", "unless",
        "until", "till", "once", "whenever", "wherever", "whoever", "whichever",
        "whatever", "whenever", "however", "howsoever", "whenever", "wherever",
        "whysoever", "whatsoever", "whosoever", "whomsoever", "whosesoever"
    ]

    for sentence in sentences:
        sentence_lower = sentence.lower()

        if len(sentence.split()) < 3:
            continue

        if filtered_sentences and sentence.strip() == filtered_sentences[-1].strip():
            continue

        sentence = re.sub(r'([!?.]){2,}', r'\1', sentence)
        sentence = re.sub(r'^[\s\-\*•]+(\d+\.?)?\s*', '', sentence)

        filler_phrases = [
            "we are looking for", "the ideal candidate", "in this role",
            "you will be responsible", "what you'll do", "your responsibilities",
            "equal opportunity employer", "eeo statement", "diversity and inclusion",
            "about the company", "our company", "who we are", "company culture",
            "benefits and perks", "what we offer", "compensation and benefits",
            "how to apply", "application process", "contact information", "travel requirements"
        ]
        for phrase in filler_phrases:
            if phrase in sentence_lower:
                sentence = sentence.replace(phrase, "", 1).strip()
                if sentence:
                    sentence = sentence[0].upper() + sentence[1:]

        words = sentence.split()
        filtered_words = []

        for i, word in enumerate(words):
            word_lower = word.lower().strip(".,!?;:\"'()[]{}")

            if word_lower in filler_words:
                if word_lower in ["and", "or", "but"] and i > 0 and i < len(words) - 1:
                    filtered_words.append(word)
                elif word_lower in ["with", "from", "to", "for"] and i > 0:
                    filtered_words.append(word)
                else:
                    continue
            else:
                filtered_words.append(word)

        if filtered_words:
            sentence = ' '.join(filtered_words)

        if sentence.strip():
            filtered_sentences.append(sentence)

    concise_text = '. '.join(filtered_sentences)
    concise_text = re.sub(r'\s+', ' ', concise_text)
    concise_text = re.sub(r'\.([A-Za-z])', r'. \1', concise_text)

    return concise_text

st.title("CV Butler")

if "job_context" not in st.session_state:
    st.session_state["job_context"] = None
if "job_text_concise" not in st.session_state:
    st.session_state["job_text_concise"] = None
if "anonymized_resumes" not in st.session_state:
    st.session_state["anonymized_resumes"] = {}
if "original_resumes" not in st.session_state:
    st.session_state["original_resumes"] = {}
if "resume_names" not in st.session_state:
    st.session_state["resume_names"] = {}
if "original_file_data" not in st.session_state:
    st.session_state["original_file_data"] = {}

job_file = st.file_uploader("Upload Job Description", type=["html"])
job_text = ""
if job_file:
    file_bytes = job_file.read()
    text_html = file_bytes.decode("utf-8")

    #! removed file writing operations for cloud compatibility
    # job_path = Path("job_description.html")
    # with open(job_path, "wb") as f:
    #     f.write(file_bytes)

    text_html_clean = text_html.encode('ascii', errors='ignore').decode('utf-8')
    
    #! removed file writing operations for cloud compatibility
    # clean_html_path = Path("job_description_clean.html")
    # with open(clean_html_path, "w", encoding="utf-8") as f:
    #     f.write(text_html_clean)

    soup = BeautifulSoup(text_html_clean, "html.parser")
    job_text = soup.get_text(separator="\n")

    #! removed file writing operations for cloud compatibility
    # txt_path = Path("job_description.txt")
    # with open(txt_path, "w", encoding="utf-8") as f:
    #     f.write(job_text)

    job_text_concise = preprocess_job_text(job_text)

    #! removed file writing operations for cloud compatibility
    # txt_concise_path = Path("job_description_concise.txt")
    # with open(txt_concise_path, "w", encoding="utf-8") as f:
    #     f.write(job_text_concise)

    #! ai generated the prompts to follow the best principles of propmt engineering.
    #! context Length: shorter prompts = faster responses. tried to make the prompt as complete as possible without making it too long.
    #! the prompt is not set up for FrieslandCampina specifically to test the job descriptions from enough real companies with mostly real resumes.
    #! even though the model is running locally, i decided to anonymize the resume data before analysis.
    #! i did it because of the uncertainty around what data the model was trained on.
    #! i wanted to make sure that the analysis did not get influenced by personal data.

    job_prompt = (
        f"Summarize this job description in three sections:\n"
        f"1. Responsibilities: Main tasks and goals\n"
        f"2. Required Skills: Technical, analytical, interpersonal\n"
        f"3. Desired Experience: Years, industry, certifications, education\n"
        f"Use bullet points.\n\n"
        f"Job Description:\n{job_text_concise}"
    )

    job_summary = ""

    with st.spinner("Analyzing job description..."):
        if gemini_configured:
            job_summary = call_gemini(job_prompt)
      #  else:
          #  st.warning("Gemini API not configured. Using local model instead.")
            #job_summary = call_ollama(job_prompt)
            
        if not job_summary:
            st.error("Failed to get job summary from any model.")
            
    st.session_state["job_context"] = job_summary
    st.session_state["job_text_concise"] = job_text_concise

    st.text("Job Description processed.")

    #! introduced batch processing to make the ux smoother and converted resume to txt as well.

resume_files = st.file_uploader(
    "Upload Resumes", type=["pdf", "docx"], accept_multiple_files=True)

#! modified process_resume function to work without temporary files
def process_resume(resume, candidate_id):
    # Extract text from resume
    if resume.name.endswith(".pdf"):
        text = ""
        with pdfplumber.open(resume) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
    elif resume.name.endswith(".docx"):
        doc = Document(resume)
        text = "\n".join([p.text for p in doc.paragraphs])
    else:
        text = ""

    # Store file data in memory instead of writing to disk
    file_data = resume.getvalue()
    
    prompt = (
        f"GDPR anonymize resume ID {candidate_id}:\n"
        f"Remove: name, address, phone, email, DOB, gender, photo, social media\n"
        f"Keep: job titles, employers, dates, locations (city), experience, education, certs, skills\n"
        f"Output anonymized data only.\n\n"
        f"Resume:\n{text}"
    )
    
    # Use Gemini for anonymization if configured, otherwise use Ollama
    if gemini_configured:
        anonymized_text = call_gemini(prompt)
    #else:
       # anonymized_text = call_ollama(prompt)
        
    return resume.name, anonymized_text, text, file_data

#! modified resume processing section to work without temporary files
if resume_files:
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for i, resume in enumerate(resume_files):
            candidate_id = f"Candidate{i+1:03d}"
            futures.append(executor.submit(process_resume, resume, candidate_id))
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            resume_name, anonymized_text, original_text, file_data = future.result()
            candidate_id = f"Candidate{i+1:03d}"
            
            st.session_state["anonymized_resumes"][candidate_id] = anonymized_text
            st.session_state["original_resumes"][candidate_id] = original_text
            st.session_state["resume_names"][candidate_id] = resume_name
            st.session_state["original_file_data"][candidate_id] = file_data
            
            progress = (i + 1) / len(resume_files)
            progress_bar.progress(progress)
            status_text.text(f"Processing resumes: {i+1}/{len(resume_files)}")
    
    progress_bar.empty()
    status_text.empty()
    st.text("All Resumes processed.")

#! modified display section to use session state instead of file paths
if st.session_state["anonymized_resumes"]:
    st.subheader("Uploaded Resumes")
    
    for candidate_id in sorted(st.session_state["anonymized_resumes"].keys()):
        resume_name = st.session_state["resume_names"][candidate_id]
        
        with st.expander(f"{candidate_id} - {resume_name}"):
            st.write("**Anonymized Version:**")
            st.write(st.session_state["anonymized_resumes"][candidate_id])
            
            if st.button(f"Show Non-Anonymized Version for {candidate_id}"):
                # Get file data from session state instead of reading from disk
                file_data = st.session_state["original_file_data"][candidate_id]
                
                st.download_button(
                    label=f"Download Original {Path(resume_name).suffix.upper()} File",
                    data=file_data,
                    file_name=resume_name,
                    mime="application/octet-stream"
                )

st.subheader("Analysis")

prompt_options = {
    "Overall Fit": (
        "Assess each candidate's overall fit:\n"
        "- Job alignment (responsibilities, tools/tech, domain, experience, qualifications)\n"
        "- Impact (achievements, career progression)\n"
        "- Skills (technical, soft: communication, problem-solving, ownership)\n"
        "- Practical fit (values, work style, stability)\n"
        "Rank the three best candidates, with one-sentence rationale per ranking, 2 sentences on suitability (strengths/weaknesses) and 2 interview questions per candidate. "
        "Refer to candidates by their respective candidate ID (e.g., Candidate001, Candidate002)."
    )
}

def create_analysis_pdf(analysis_type, result, job_context=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.set_font_size(16)
    pdf.cell(0, 10, f"CV Analysis Report: {analysis_type}", ln=True, align='C')
    pdf.ln(10)

    pdf.set_font_size(10)
    pdf.cell(
        0, 10, f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(10)

    if job_context:
        pdf.set_font_size(12)
        pdf.cell(0, 10, "Job Description Summary:", ln=True)
        pdf.set_font_size(10)
        pdf.multi_cell(0, 10, job_context)
        pdf.ln(10)

    pdf.set_font_size(12)
    pdf.cell(0, 10, "Analysis Result:", ln=True)
    pdf.set_font_size(10)
    pdf.multi_cell(0, 10, result)

    return pdf

for keyword, full_prompt_text in prompt_options.items():
    if st.button(f"{keyword}"):
        if not st.session_state["job_context"] or not st.session_state["anonymized_resumes"]:
            st.warning("Please upload and process both job description and resumes first.")
        else:
            with st.spinner(f"Running analysis..."):
                # Debug: Check what's in session state
                st.write("Debug: Job context exists:", bool(st.session_state["job_context"]))
                st.write("Debug: Number of anonymized resumes:", len(st.session_state["anonymized_resumes"]))
                
                combined_resumes_text = "\n\n".join(
                    f"{candidate_id}:\n{text}"
                    for candidate_id, text in st.session_state["anonymized_resumes"].items()
                )

                full_prompt = (
                    f"Job Description Context:\n{st.session_state['job_context']}\n\n"
                    f"Resumes:\n{combined_resumes_text}\n\n"
                    f"Instruction:\n{full_prompt_text}"
                )

                # Debug: Show the prompt being sent
                st.write("Debug: Prompt length:", len(full_prompt))
                
                if gemini_configured:
                    final_result = call_gemini(full_prompt)
                #else:
                    #final_result = call_ollama(full_prompt)
                
                # Debug: Show the result
                st.write("Debug: Result length:", len(final_result) if final_result else 0)

            st.text_area(f"{keyword} Analysis Result", value=final_result, height=300)

            pdf = create_analysis_pdf(
                keyword,
                final_result,
                st.session_state.get("job_context"),
            )

            pdf_buffer = io.BytesIO()
            pdf.output(pdf_buffer)
            pdf_data = pdf_buffer.getvalue()

            st.download_button(
                label=f"Download {keyword} Analysis as PDF",
                data=pdf_data,
                file_name=f"cv_analysis_{keyword.lower().replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )

#! custom prompt section.
#! giving the correct context to the model with the job description and resumes.

custom_prompt = st.text_area("Enter custom prompt here:", height=100)
if st.button("Send"):
    if custom_prompt.strip() == "":
        st.warning("Please enter a prompt")
    else:
        if not st.session_state["job_context"] or not st.session_state["anonymized_resumes"]:
            st.warning("Please upload and process both job description and resumes first.")
        else:
            combined_resumes_text = "\n\n".join(
                f"{candidate_id}:\n{text}"
                for candidate_id, text in st.session_state["anonymized_resumes"].items()
            )

            full_prompt = (
                f"Job Description Context:\n{st.session_state['job_context']}\n\n"
                f"Resumes:\n{combined_resumes_text}\n\n"
                f"Instruction:\n{custom_prompt}"
            )

            with st.spinner("Generating response..."):
                if gemini_configured:
                    result = call_gemini(full_prompt)
                #else:
                 #   result = call_ollama(full_prompt)

            st.text_area("Custom Analysis Result", value=result, height=300)

            pdf = create_analysis_pdf(
                "Custom Analysis",
                result,
                st.session_state.get("job_context"),
            )
            
            pdf_buffer = io.BytesIO()
            pdf.output(pdf_buffer)
            pdf_data = pdf_buffer.getvalue()
            
            st.download_button(
                label="Download Custom Analysis as PDF",
                data=pdf_data,
                file_name=f"custom_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )