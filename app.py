import streamlit as st
from pathlib import Path
import pdfplumber
from docx import Document
import pypandoc
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from tqdm import tqdm
import re


#!! sbert similarity scoring for ranking.
#!! generate interview questions per candidate.
#!! export data to pdf.

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

#! adding a pre-procesing step to make job description more concise. this should make the analysis faster by making the prompt smaller.
#! decided against pre-processing resumes as they are generally concise already.
#! if the pre-processing step negatively affects a candidate's evaluation, then that would be unfair.
#! pre-processing job description would impact all candidates equally.


def preprocess_job_text(text):
    """Preprocess job description text to make it more concise while preserving context."""
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

    job_text_concise = preprocess_job_text(job_text)

    txt_concise_path = Path("job_description_concise.txt")
    with open(txt_concise_path, "w", encoding="utf-8") as f:
        f.write(job_text_concise)

    #! ai generated the prompts to follow the best principles of propmt engineering.
    #! context Length: shorter prompts = faster responses. tried to make the prompt as complete as possible without making it too long.
    #! the prompt is not set up for FrieslandCampina specifically to test the job descriptions from enough real companies with mostly real resumes.
    #! even though the model is running locally, i decided to anonymize the resume data before analysis.
    #! i did it because of the uncertainty around what data the model was trained on.
    #! i wanted to make sure that the analysis did not get influenced by personal data.

    if "job_context" not in st.session_state and job_text.strip():
        job_prompt = (
            f"Summarize this job description in three sections:\n"
            f"1. Responsibilities: Main tasks and goals\n"
            f"2. Required Skills: Technical, analytical, interpersonal\n"
            f"3. Desired Experience: Years, industry, certifications, education\n"
            f"Use bullet points. Paraphrase, don't copy. For candidate comparison.\n\n"
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
        f"GDPR anonymize resume ID {candidate_id}:\n"
        f"Remove: name, address, phone, email, DOB, gender, photo, social media\n"
        f"Keep: job titles, employers, dates, locations (city), experience, education, certs, skills\n"
        f"Output anonymized data only.\n\n"
        f"Resume:\n{text}"
    )
    anonymized_text = call_ollama(prompt)

    return resume.name, anonymized_text, text


if resume_files:
    progress_bar = st.progress(0)
    status_text = st.empty()

    if "anonymized_resumes" not in st.session_state:
        st.session_state["anonymized_resumes"] = {}
    if "original_resumes" not in st.session_state:
        st.session_state["original_resumes"] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for i, resume in enumerate(resume_files):
            candidate_id = f"Candidate{i+1:03d}"
            futures.append(executor.submit(
                process_resume, resume, candidate_id))

        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            resume_name, anonymized_text, original_text = future.result()

            st.session_state["anonymized_resumes"][resume_name] = anonymized_text
            st.session_state["original_resumes"][resume_name] = original_text

            progress = (i + 1) / len(resume_files)
            progress_bar.progress(progress)
            status_text.text(f"Processing resumes: {i+1}/{len(resume_files)}")

    progress_bar.empty()
    status_text.empty()

    st.text("All Resumes processed.")


#! the solution allows for multiple types of analysis along with a custom prompt option that the user can input.
#! the prompts would be made more specialized when setting this up for the company.

st.subheader("Analysis")

prompt_options = {
    "Alignment with Job Requirements": (
        "Evaluate each candidate's job alignment:\n"
        "- Responsibilities match\n"
        "- Tools, technologies, domain expertise\n"
        "- Seniority level\n"
        "- Qualifications (degrees, certifications, languages)\n"
        "Provide bullet summary per candidate. Rank from best to worst."
    ),

    "Demonstrated Impact and Outcomes": (
        "Assess each candidate's impact:\n"
        "- Measurable results (cost savings, revenue, efficiency, project success)\n"
        "- Career progression, responsibilities, promotions\n"
        "Provide brief summary per candidate. Rank by impact."
    ),

    "Core Skills and Competencies": (
        "Evaluate each candidate's skills:\n"
        "- Hard skills (role-specific)\n"
        "- Soft skills (communication, collaboration, stakeholder management, problem-solving, ownership)\n"
        "Summarize skill fit per candidate. Rank by skills match."
    ),

    "Overall Fit": (
        "Assess each candidate's overall fit:\n"
        "- Job alignment (responsibilities, tools/tech, domain, experience, qualifications)\n"
        "- Impact (achievements, career progression)\n"
        "- Skills (technical, soft: communication, problem-solving, ownership)\n"
        "- Practical fit (values, work style, stability)\n"
        "For each candidate: 2-3 sentences on suitability (strengths/weaknesses).\n"
        "Rank all candidates from most to least suitable, with one-sentence rationale per ranking."
    )
}
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
