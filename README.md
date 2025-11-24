# CVButler - AI-Powered ATS

🚀 An intelligent Applicant Tracking System that uses LLM-powered analysis to rank candidates against job descriptions, providing detailed explanations and bias-free evaluation.

## Features

- 🤖 **AI-Powered Matching**: Uses local LLMs (Ollama) with OpenAI fallback for candidate-job matching
- 🛡️ **Privacy-Focused**: Anonymizes PII and removes bias indicators before analysis
- 📊 **Detailed Explanations**: Provides ranking rationale with text citations
- 💾 **Persistent Storage**: JSON-based data persistence (no database required)
- 🎯 **Top Candidate Ranking**: Returns top 3 candidates with comprehensive analysis

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit     │────│    FastAPI      │────│   Ollama/OpenAI │
│   Frontend      │    │   Backend       │    │   LLM Models    │
│                 │    │                 │    │                 │
│ - File upload   │    │ - Text extract  │    │ - Llama2 7B     │
│ - Results view  │    │ - Anonymization │    │ - GPT fallback  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   JSON Storage  │
                    │    (data/)      │
                    │                 │
                    │ - jobs.json     │
                    │ - resumes.json  │
                    │ - rankings/     │
                    └─────────────────┘
```

## Quick Start

### Prerequisites

1. **Python 3.8+** installed
2. **Ollama** for local LLM inference (optional, OpenAI fallback available)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/ritwyck/cvbutler.git
cd cvbutler
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. (Optional) Set up Ollama for local LLM inference:

```bash
# Install Ollama from https://ollama.ai/
ollama pull llama2:7b
```

### Running the Application

1. Start the backend:

```bash
PYTHONPATH=/Users/wiksrivastava/Desktop/CVButler python backend/main.py
```

2. Start the frontend (in a new terminal):

```bash
streamlit run frontend/app.py
```

3. Open http://localhost:8501 in your browser

Note: Upload your own job descriptions and resumes through the web interface.

## API Endpoints

### Backend (FastAPI) - Port 8000

- `GET /` - Health check
- `GET /health` - Detailed health status
- `POST /api/jobs/upload` - Upload job description
- `POST /api/resumes/upload` - Upload candidate resumes
- `POST /api/analyze/{job_id}` - Run candidate analysis
- `GET /api/jobs` - List all jobs
- `GET /api/results/{job_id}` - Get analysis results

### Usage Example

```python
import requests

# Upload job
files = {"file": open("job_description.pdf", "rb")}
job_response = requests.post("http://localhost:8000/api/jobs/upload", files=files)
job_id = job_response.json()["job_id"]

# Upload resumes
files = [("files", open(f"resume_{i}.pdf", "rb")) for i in range(5)]
resume_response = requests.post("http://localhost:8000/api/resumes/upload", files=files)

# Run analysis
analysis = requests.post(f"http://localhost:8000/api/analyze/{job_id}")
results = analysis.json()
```

## LLM Integration

CVButler supports multiple LLM providers:

### Primary: Ollama (Recommended)

- Local inference with privacy preservation
- No API costs or usage limits
- Works offline
- Models: Mistral, Llama2, etc.

### Fallback: OpenAI

- Set `OPENAI_API_KEY` environment variable
- Automatic fallback when Ollama unavailable
- GPT-3.5-turbo for analysis

## Data Processing Pipeline

1. **Text Extraction**: PDF/DocX parsing using PyPDF2/python-docx
2. **Anonymization**:
   - NER-based entity removal (spaCy)
   - Regex patterns for PII (emails, phones, addresses)
   - Bias indicator removal (age, gender references)
3. **LLM Analysis**: Prompt-engineered scoring and explanation generation
4. **Ranking**: Composite scoring with detailed citations

## Configuration

### Customization

- **Prompts**: Modify templates in `utils/data_models.py`
- **LLM Models**: Change models in `utils/llm_wrapper.py`
- **Anonymization**: Extend patterns in `utils/anonymization.py`

## Data Storage

The application stores uploaded job descriptions, resumes, and analysis results as JSON files in a local data directory. No external databases are required.

## Deployment

### Local Development

- Backend: FastAPI on localhost:8000
- Frontend: Streamlit on localhost:8501
- Data: Local JSON files in `data/` directory

### Production Deployment

#### Streamlit Cloud (Recommended)

1. Push to GitHub repository
2. Deploy on Streamlit Cloud
3. Add Ollama/OpenAI integration as needed

#### Docker Deployment

```bash
# Build container
docker build -t cvbutler .

# Run container
docker run -p 8501:8501 cvbutler
```

#### Cloud Platforms

- **Railway**: Easy Python deployment
- **Render**: Free tier available
- **Heroku**: Traditional option

## Security & Privacy

- **Local Processing**: Text analysis happens locally when using Ollama
- **Anonymization**: Automatic PII removal before LLM processing
- **No Data Storage**: Only file metadata; no external data collection
- **Bias Mitigation**: Removes demographic indicators from analysis

## Performance

- **Local LLM**: ~30-60 seconds per candidate analysis
- **OpenAI**: ~5-10 seconds per candidate analysis
- **Batch Processing**: Optimized for multiple candidates
- **M1 Mac Optimized**: Full Apple Silicon support

## Limitations

- Single language support (English only)
- Text-based analysis (no image parsing)
- No real-time collaboration features
- JSON storage scales to ~1000 jobs/resumes

## Troubleshooting

### Common Issues

1. **"Backend not running"**

   - Ensure backend is started: `cd backend && python main.py`
   - Check port 8000 isn't blocked

2. **"LLM not available"**

   - Install Ollama: `brew install ollama` (macOS)
   - Pull model: `ollama pull llama2:7b`
   - Or set OpenAI API key

3. **Import errors**

   - Install dependencies: `pip install -r requirements.txt`
   - Download spaCy model: `python -m spacy download en_core_web_sm`

4. **File upload issues**
   - Supported formats: PDF, DOCX, TXT
   - Max file size: Limited by Streamlit (200MB default)

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Make changes and test thoroughly
4. Submit pull request with description

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Built for FrieslandCampina intern assignment
- Uses Ollama for local LLM inference
- Inspired by modern ATS solutions with AI/ML integration
