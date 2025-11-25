import streamlit as st
from pathlib import Path
import pdfplumber
from docx import Document
import pypandoc
import requests

st.title("CV Butler")


def call_ollama(prompt, model="gemma3:4b"):
    payload = {"model": model, "prompt": prompt, "stream": False}
    resp = requests.post("http://localhost:11434/api/generate", json=payload)
    return resp.json().get("response", "")


# --- Job Description Upload ---
job_file = st.file_uploader("Upload Job Description", type=["html"])
job_text = ""
if job_file:
    # Read the file once
    file_bytes = job_file.read()
    text_html = file_bytes.decode("utf-8")

    # Save original HTML
    job_path = Path("job_description.html")
    with open(job_path, "wb") as f:
        f.write(file_bytes)

    # Remove problematic Unicode characters (e.g., emojis)
    text_html_clean = text_html.encode(
        'ascii', errors='ignore').decode('utf-8')
    clean_html_path = Path("job_description_clean.html")
    with open(clean_html_path, "w", encoding="utf-8") as f:
        f.write(text_html_clean)

    # Convert cleaned HTML -> PDF
    output_pdf = Path("job_description.pdf")
    try:
        pypandoc.convert_file(str(clean_html_path), 'pdf',
                              outputfile=str(output_pdf))

    except Exception as e:
        st.error(f"The job description is not in the desired format: {e}")

    # Extract text from cleaned HTML for the model prompt
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(text_html_clean, "html.parser")
    job_text = soup.get_text(separator="\n")

    # --- Send Job Description Understanding Prompt (Background) ---
    if "job_context" not in st.session_state and job_text.strip():
        job_prompt = (
            f"Read and fully comprehend the following job description. Extract and summarize its key responsibilities, required skills, and desired experience, "
            f"ensuring the information is clear and concise for HR evaluation. Present the summary in a structured, labeled format with three sections: "
            f"'Responsibilities': List main tasks and goals. 'Required Skills': List technical, analytical, and interpersonal skills. "
            f"'Desired Experience': Detail years of experience, industry background, certifications, or education. Organize each section with bullet points for readability. "
            f"Do not copy text directly; paraphrase for clarity. This structured summary will be used to compare candidate resumes for role fit.\n\n"
            f"Job Description:\n{job_text}"
        )

        # Run in background with spinner
        with st.spinner("Analyzing job description..."):
            job_summary = call_ollama(job_prompt)
            st.session_state["job_context"] = job_summary

    st.text("Job Description processed.")

# --- Resume Upload ---
resume_files = st.file_uploader(
    "Upload Resumes", type=["pdf", "docx"], accept_multiple_files=True
)

# Dictionary to store anonymized resumes
if "anonymized_resumes" not in st.session_state:
    st.session_state["anonymized_resumes"] = {}

if resume_files:
    candidate_counter = 1  # Start numbering candidates

    for resume in resume_files:
        if resume.name not in st.session_state["anonymized_resumes"]:
            # Extract text from PDF or DOCX
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

            # Anonymization prompt with unique candidate number
            # e.g., Candidate001, Candidate002
            candidate_id = f"Candidate{candidate_counter:03d}"
            prompt = (
                f"Act as a senior HR recruiter and perform GDPR-compliant anonymization. "
                f"For the following resume, remove all personal identifiers such as full name, address, phone number, email, date of birth, gender, photo, links to social media, "
                f"and any other contact details. Assign the candidate reference number: {candidate_id}. "
                f"Retain job titles, employers, dates, locations (in non-identifiable form, e.g., city only), work experience, education, certifications, and skills. "
                f"Ensure the output contains only anonymized data or masked placeholders for redacted fields, ready for blind recruitment evaluation. "
                f"Resume:\n{text}"
            )
            anonymized_text = call_ollama(prompt)
            st.session_state["anonymized_resumes"][resume.name] = anonymized_text

            candidate_counter += 1  # Increment for next candidate

    st.text("All Resumes processed.")


# --- Custom Analysis Prompts ---
st.subheader("Analysis")

# Define your 3-4 custom prompts (keywords shown in the UI, full prompt used internally)
prompt_options = {
    "Alignment with Job Requirements": "Act as a senior HR recruiter. For each candidate resume, evaluate the alignment with the job description focusing on: Matching responsibilities, Relevant tools, technologies, and domain expertise. Appropriate seniority level. Meeting required qualifications such as degrees, certifications, languages. Provide a concise bullet summary per candidate and rank all candidates from best to worst alignment.",
    "Demonstrated Impact and Outcomes": "Act as a senior HR recruiter. For each candidate resume, assess the evidence of measurable results such as cost savings, revenue growth, efficiency improvements, and successful project delivery. Consider career progression, increased responsibilities, and promotions. Provide a brief summary for each candidate and rank them based on demonstrated impact.",
    "Core Skills and Competencies": "Act as a senior HR recruiter. For each candidate resume, evaluate role-specific hard skills and relevant soft skills like communication, collaboration, stakeholder management, problem-solving, and ownership. Summarize the skill fit per candidate and rank candidates according to skills match.",
    "Overall Fit": "Act as a senior HR recruiter evaluating candidate resumes against a given job description analysis. For each candidate, assess overall fit by considering: Alignment with job responsibilities, tools/technologies, domain expertise, seniority level, and qualifications (degrees, certifications, languages, work authorization). Demonstrated impact and outcomes such as measurable achievements and career progression. Core technical and transferable soft skills including communication, problem-solving, and ownership. Practical fit including values, work style, availability, and stability. For each candidate, provide 2-3 sentences explaining their overall suitability, with strengths and weaknesses. Then produce a final ranked list of all candidates from most to least suitable for the role, with a one-sentence rationale for each candidate’s ranking."}

# Show buttons with keywords only
for keyword, full_prompt_text in prompt_options.items():
    if st.button(f"{keyword}"):
        if "job_context" not in st.session_state or not st.session_state["anonymized_resumes"]:
            st.warning(
                "Please upload and process both job description and resumes first.")
        else:
            with st.spinner(f"Running analysis..."):
                # Build a combined prompt with job description context and all anonymized resumes
                combined_resumes_text = "\n\n".join(
                    f"{name}:\n{text}" for name, text in st.session_state["anonymized_resumes"].items()
                )
                full_prompt = (
                    f"Job Description Context:\n{st.session_state['job_context']}\n\n"
                    f"Resumes:\n{combined_resumes_text}\n\n"
                    f"Instruction:\n{full_prompt_text}"
                )
                final_result = call_ollama(full_prompt)
                st.text_area(f"{keyword} Analysis Result",
                             value=final_result, height=300)

# --- Mini Chatbox ---
custom_prompt = st.text_area("Enter custom prompt here:", height=100)
if st.button("Send"):
    if custom_prompt.strip() == "":
        st.warning("Please enter a prompt")
    else:
        if "job_context" not in st.session_state or not st.session_state["anonymized_resumes"]:
            st.warning(
                "Please upload and process both job description and resumes first.")
        else:
            combined_resumes_text = "\n\n".join(
                f"{name}:\n{text}" for name, text in st.session_state["anonymized_resumes"].items()
            )
            full_prompt = (
                f"Job Description Context:\n{st.session_state['job_context']}\n\n"
                f"Resumes:\n{combined_resumes_text}\n\n"
                f"User Instruction:\n{custom_prompt}"
            )
            response = call_ollama(full_prompt)
            st.text_area("Response", value=response, height=300)
