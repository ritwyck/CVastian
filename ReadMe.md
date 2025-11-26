# CVastian: AI-Powered CV Analysis Tool

CVastian is a Streamlit-based web application that automates the candidate evaluation process by analyzing job descriptions against multiple resumes using AI models. It provides structured assessments, rankings, and PDF reports to help HR teams make data-driven hiring decisions.

## Architecture Overview

CVastian follows a multi-layered architecture designed for scalability, privacy, and cloud deployment:

### Core Components

- **Web Interface**: Streamlit application handling file uploads, progress tracking, and results display
- **Text Processing Layer**: Handles PDF/DOCX file extraction, HTML parsing, and text cleaning
- **Anonymization Engine**: AI-powered GDPR-compliant data cleaning to remove personally identifiable information
- **AI Analysis Engine**: Dual-model system supporting both local Ollama and Google Gemini API
- **Report Generation**: Automatic PDF report creation with analysis results and job context

### Data Flow

1. **Input Processing**: Job descriptions (HTML/PDF) and resume files (PDF/DOCX) are uploaded
2. **Text Extraction**: Documents are converted to clean .txt format to best support prompting. The documents were pre-processed to make them smaller, to make the process of working with an LLM better.
3. **Job Summarization**: AI generates structured summaries of responsibilities, skills, and experience requirements
4. **Resume Anonymization**: Personal data is removed while preserving professional qualifications as per the GDPR regulation.
5. **Candidate Analysis**: Each resume is evaluated against job requirements with structured scoring
6. **Report Generation**: Results compiled into downloadable PDF reports
7. **Prompt Engineering**: All prompts were engineered to provide the best results with the least number of tokens.

### Model Architecture

```
┌─────────────────┐
│   User Interface │
│    (Streamlit)   │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐           ┌─────────────────┐
│ File Uploads    │ ◄─────────┤ Job Description │
│ - Resume PDFs   │           │ - HTML/PDF      │
│ - Job Desc      │           └─────────────────┘
└─────────┬───────┘                   │
          │                           ▼
          │               ┌─────────────────┐
          │               │ Job Preprocessing│
          │               │ - Text cleaning  │
          │               │ - Conciseness    │
          │               └─────────────────┘
          │                           │
          └───────► [AI Models] ──────┤
                      ├─ Gemini API (Primary)
                      ├─ Ollama Gemma3
                                │
                ┌───────────────┼───────────────┐
                │                               │
                ▼                               ▼
     ┌─────────────────┐             ┌─────────────────┐
     │ Resume Processing│            │ Job Analysis &  │
     │ - PDF/DOCX       │            │   Summary       │
     │ - Text extraction│            │ - Responsibilities│
     └─────────┬───────┘             │ - Skills Required │
                │                    └─────────────────┘
                │                              │
                │                              │
                ▼                              │
     ┌─────────────────┐                       │
     │ Anonymization   │                       │
     │ - Remove PII    │                       │
     │ - GDPR compliant│                       │
     └─────────┬───────┘                       │
               │                               │
               ▼        ◄──────────────────────│
     ┌─────────────────┐
     │ Candidate       │
     │ Evaluation      │
     │ - Fit analysis  │
     │ - Ranking       │
     │ - Interview Qs  │
     └─────────┬───────┘
                │
                ▼
     ┌─────────────────┐
     │ Report Generation│
     │ - Text results   │
     │ - PDF export     │
     └─────────────────┘
```

## How to Run the App

### Prerequisites

- Python 3.8 or higher
- For local model (recommended for privacy): [Ollama](https://ollama.com/) installed. This model utilises Ollama - gemma3:4b. Should you want to use a different model, change the model that is being fetched in the code. Consider your device limitations when picking a model and its caliberation. This code was run on M1 Apple Silicon 8gb, so gemma3:4b was the best performing model this device could _barely_ handle. It was caliberated for low temperature - reduce likelihood of hallucinations.
- For cloud model (faster processing): Google Gemini API key. Model can be picked and determined in the code here. However, consider the prompt limits and model availability if you have a free account.

### Installation and Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/ritwyck/CVastian.git
   cd CVastian
   ```

2. **Install Python dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**

   - Copy or create `.env` file:
     ```
     GOOGLE_API_KEY=your_gemini_api_key_here
     ```
   - If not using Gemini, you can leave this as default

4. **Install and start Ollama (for local model only)**

   ```bash
   # Pull the Gemma3 model (4B parameter version for local hardware constraints)
   ollama pull gemma3:4b

   # Start Ollama server in another terminal
   ollama serve
   ```

5. **Run the application**

   ```bash
   # For development
   streamlit run app.py

   # Or use the provided script
   bash start.sh
   ```

6. **Access the application**
   - Open browser to `http://localhost:8501`
   - Upload job description and resume files
   - Run analysis and generate reports

## How to Deploy

### Production Deployment

CVastian is designed for easy cloud deployment with headless Streamlit configuration.

#### Environment Setup

Set these environment variables for production:

```bash
ENVIRONMENT=production
PORT=8501  # or your hosting platform's assigned port
GOOGLE_API_KEY=your_production_api_key
```

#### Using the Start Script

The `start.sh` script configures Streamlit for production:

```bash
bash start.sh
```

#### Cloud Platform Deployment

**Render App Platform:**

- Use `start.sh` as the start command
- Set environment variables in platform dashboard
- Ensure Ollama is available locally or use Gemini API only

**Docker Deployment:**

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8501

# For Ollama local model - requires Ollama host accessible
CMD ["streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

### Model Selection for Deployment

- **Local Ollama**: Better privacy, works offline, tortures your hardware. I used my laptop as room heating for two days.
- **Google Gemini API**: Faster processing, cloud reliability, requires API key. Loses purpose when wanting to anonymise data.

## Key Design Decisions

### 1. Local vs Cloud AI Models

The application was developed with local Ollama models (Gemma3:4B) due to security and privacy. However, the final design prioritizes cloud Gemini Api due to local hardware limitations during development. The local approach ensures data never leaves the deployment environment while maintaining reasonable performance on modern hardware, reflecting concerns about running HR-sensitive candidate data .

### 2. Resume Anonymization

To prevent unconscious bias in AI analysis, all resumes undergo GDPR-compliant anonymization that removes names, addresses, emails, phone numbers, photos, and other personal identifiers. Only professional qualifications are preserved. This was implemented because of uncertainty about LLM training data and potential bias amplification.

### 3. Job Description Pre-processing

Job descriptions are pre-processed for conciseness to reduce prompt length and improve analysis speed. However, resumes are kept in their original form to maintain fairness - shortening resumes could disadvantage candidates with longer, more detailed backgrounds.

### 4. In-Memory Processing and Session State

Instead of writing files to disk, the application uses Streamlit's session state for temporary storage. This enables cloud deployment on platforms without persistent storage and supports multi-file batch processing. It also reduces cleanup overhead and simplifies the user experience by keeping everything in memory during analysis. I was intially storing the files on my device locally, which was an error that took me a while to fix when moving from local host to Render.

### 5. Batch Processing Implementation

Added concurrent processing for multiple resumes using ThreadPoolExecutor to prevent blocking the UI during large batch operations. This significantly improves user experience when analyzing many candidates at once, though it requires careful state management to handle asynchronous completion. Especially useful for when running the local llm, as the analysis sometimes took upwards of 8 minutes from start to end.

## Areas of Improvement

Add multi-language support.
Include nested-prompting to get better responses.
Include a toggle to allow the user decide if they wanted interview questions.
Improve UI by integrating the text clearly.
Utilise S-Bert model to check for similarity between job listing and resumes.

## The ReadMe file was created with the help of an LLM. It was asked to analyse all the comments that explained the decision-making process and consider the technical factors. Whatever I felt was missed or not explained by the model was added by me.

## License

This project is licensed under the terms specified in the LICENSE file.
