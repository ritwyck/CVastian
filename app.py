import streamlit as st
from pathlib import Path
import pdfplumber
from docx import Document
import pypandoc
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from tqdm import tqdm

#!! convert everything to .txt
#!! Context Length: Shorter prompts = faster responses. Keep under 2048 tokens if possible.
#!! language support would be nice.
#!! sbert similarity scoring for ranking.
#!! generate interview questions per candidate.
#!! comparison table for candidates
#!! export data to pdf.
#!! pre process job description and the resume to get faster responses.
#!! click on resume to show non-anonymized version.
#!! visualise ranking with bar chart.

#! gemma3 model is being used here, the best that my hardware could support.
#! attempted using larger models but ran into issues.
#! the solution was inspired from:
#! • https://www.youtube.com/watch?v=bp2eev21Qfo - this was to understand how models are set up locally and called via API.
#! • https://www.youtube.com/watch?v=EECUXqFrwbc&list=WL&index=2 - this was to understand how to structure the solution.
#! naturally a cloud based gemini api integrated solution would be faster and more powerful, but a local system provides more security.


#! model configuration for better responses.
model_config = {
    "temperature": 0.2,
    "repeat_penalty": 1.15
}

st.title("CV Butler")


def call_ollama(prompt, model="gemma3:4b"):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": model_config
    }
    resp = requests.post("http://localhost:11434/api/generate", json=payload)
    return resp.json().get("response", "")

 #! file had to be converted to .txt from html because ollama model works best with plain text input.
    #! this also explains why the ascii encoding step was needed.
    #! initially converted to pdf but then optimised the process.


job_file = st.file_uploader("Upload Job Description", type=["html"])
job_text = ""
if job_file:
    file_bytes = job_file.read()
    text_html = file_bytes.decode("utf-8")

    job_path = Path("job_description.html")
    with open(job_path, "wb") as f:
        f.write(file_bytes)

    text_html_clean = text_html.encode(
        'ascii', errors='ignore').decode('utf-8')
    clean_html_path = Path("job_description_clean.html")
    with open(clean_html_path, "w", encoding="utf-8") as f:
        f.write(text_html_clean)

    soup = BeautifulSoup(text_html_clean, "html.parser")
    job_text = soup.get_text(separator="\n")

    txt_path = Path("job_description.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(job_text)

    #! ai generated the prompts to follow the best principles of propmt engineering.
    #! the prompt is not set up for FrieslandCampina specifically to test the job descriptions from enough real companies with mostly real resumes.
    #! even though the model is running locally, i decided to anonymize the resume data before analysis.
    #! i did it because of the uncertainty around what data the model was trained on.
    #! i wanted to make sure that the analysis did not get influenced by personal data.

    if "job_context" not in st.session_state and job_text.strip():
        job_prompt = (
            f"Read and fully comprehend the following job description. Extract and summarize its key responsibilities, required skills, and desired experience, "
            f"ensuring the information is clear and concise for HR evaluation. Present the summary in a structured, labeled format with three sections: "
            f"'Responsibilities': List main tasks and goals. 'Required Skills': List technical, analytical, and interpersonal skills. "
            f"'Desired Experience': Detail years of experience, industry background, certifications, or education. Organize each section with bullet points for readability. "
            f"Do not copy text directly; paraphrase for clarity. This structured summary will be used to compare candidate resumes for role fit.\n\n"
            f"Job Description:\n{job_text}"
        )

        with st.spinner("Analyzing job description..."):
            job_summary = call_ollama(job_prompt)
            st.session_state["job_context"] = job_summary

    st.text("Job Description processed.")

#! introduced batch processing to make the ux smoother and converted resume to txt as well.

resume_files = st.file_uploader(
    "Upload Resumes", type=["pdf", "docx"], accept_multiple_files=True
)


def process_resume(resume, candidate_id):
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

    txt_path = Path(f"resume_{candidate_id}_original.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    prompt = (
        f"Act as a senior HR recruiter and perform GDPR-compliant anonymization. "
        f"For the following resume, remove all personal identifiers such as full name, address, phone number, email, date of birth, gender, photo, links to social media, "
        f"and any other contact details. Assign the candidate reference number: {candidate_id}. "
        f"Retain job titles, employers, dates, locations (in non-identifiable form, e.g., city only), work experience, education, certifications, and skills. "
        f"Ensure the output contains only anonymized data or masked placeholders for redacted fields, ready for blind recruitment evaluation. "
        f"Resume:\n{text}"
    )
    anonymized_text = call_ollama(prompt)

    anonymized_txt_path = Path(f"resume_{candidate_id}_anonymized.txt")
    with open(anonymized_txt_path, "w", encoding="utf-8") as f:
        f.write(anonymized_text)

    return resume.name, anonymized_text


if resume_files:
    progress_bar = st.progress(0)
    status_text = st.empty()

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for i, resume in enumerate(resume_files):
            candidate_id = f"Candidate{i+1:03d}"
            futures.append(executor.submit(
                process_resume, resume, candidate_id))

        anonymized_resumes = {}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            resume_name, anonymized_text = future.result()
            anonymized_resumes[resume_name] = anonymized_text

            progress = (i + 1) / len(resume_files)
            progress_bar.progress(progress)
            status_text.text(f"Processing resumes: {i+1}/{len(resume_files)}")

    st.session_state["anonymized_resumes"] = anonymized_resumes

    progress_bar.empty()
    status_text.empty()

    st.text("All Resumes processed.")

st.subheader("Analysis")

#! the solution allows for multiple types of analysis along with a custom prompt option that the user can input.
#! the prompts would be made more specialized when setting this up for the company.

prompt_options = {
    "Alignment with Job Requirements": "Act as a senior HR recruiter. For each candidate resume, evaluate the alignment with the job description focusing on: Matching responsibilities, Relevant tools, technologies, and domain expertise. Appropriate seniority level. Meeting required qualifications such as degrees, certifications, languages. Provide a concise bullet summary per candidate and rank all candidates from best to worst alignment.",
    "Demonstrated Impact and Outcomes": "Act as a senior HR recruiter. For each candidate resume, assess the evidence of measurable results such as cost savings, revenue growth, efficiency improvements, and successful project delivery. Consider career progression, increased responsibilities, and promotions. Provide a brief summary for each candidate and rank them based on demonstrated impact.",
    "Core Skills and Competencies": "Act as a senior HR recruiter. For each candidate resume, evaluate role-specific hard skills and relevant soft skills like communication, collaboration, stakeholder management, problem-solving, and ownership. Summarize the skill fit per candidate and rank candidates according to skills match.",
    "Overall Fit": "Act as a senior HR recruiter evaluating candidate resumes against a given job description analysis. For each candidate, assess overall fit by considering: Alignment with job responsibilities, tools/technologies, domain expertise, seniority level, and qualifications (degrees, certifications, languages, work authorization). Demonstrated impact and outcomes such as measurable achievements and career progression. Core technical and transferable soft skills including communication, problem-solving, and ownership. Practical fit including values, work style, availability, and stability. For each candidate, provide 2-3 sentences explaining their overall suitability, with strengths and weaknesses. Then produce a final ranked list of all candidates from most to least suitable for the role, with a one-sentence rationale for each candidate’s ranking."}

for keyword, full_prompt_text in prompt_options.items():
    if st.button(f"{keyword}"):
        if "job_context" not in st.session_state or not st.session_state["anonymized_resumes"]:
            st.warning(
                "Please upload and process both job description and resumes first.")
        else:
            with st.spinner(f"Running analysis..."):

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

#! custom prompt section.
#! giving the correct context to the model with the job description and resumes.

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
