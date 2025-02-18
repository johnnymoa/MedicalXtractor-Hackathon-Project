# 🏥 MedicalXtractor (MedXTract)

A web-based application for managing medical documents, prescriptions, and patient information. Built with Python Flask and modern web technologies.

*"Because decoding a medical history shouldn't take longer than a consultation!"* ⚕️🤖

## 📢 Project Overview

**The Problem**: 
Medical professionals, especially new doctors, face the challenge of processing extensive medical records (often 100+ pages) during time-sensitive consultations. This manual process is time-consuming and risks missing critical information.

**Our Solution**: 
MedXTract transforms complex medical documents into structured, easily digestible information through:
- 🕒 **Prescription Timeline**: Track active and expired medications
- 🎯 **Structured Medical Summary**: Quick access to key information:
  - Pathologies
  - Allergies
  - Current treatments
- 🔍 **Smart Detection**: AI-powered extraction of critical medical information

*"It's like CTRL+F, but Matrix version for busy doctors."* 💊💻

## Features

- Document management and summarization
- Prescription tracking and analysis
- Patient records organization
- Secure dashboard interface
- AI-powered information extraction

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Docker (optional, for containerized deployment)

### Environment Setup

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Configure your `.env` file with the following required variables:
```env
# Required for AI document processing
MISTRAL_API_KEY=your_mistral_api_key

# Database connection
DATABASE_URL=your_database_url

# Application security
SECRET_KEY=your_secret_key
```

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/johnnymoa/team200
cd team200
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the development server:
```bash
python app.py
```

The application will be available at `http://localhost:8080`

### Docker Deployment

1. Build the Docker image:
```bash
docker build --no-cache --platform=linux/amd64 -t rg.fr-par.scw.cloud/your-namespace-name/your-app-name .
```

2. Run the container:
```bash
docker run -p 5000:8080 \
  --env-file .env \
  -d rg.fr-par.scw.cloud/your-namespace-name/your-app-name:latest
```

The application will be available at `http://localhost:5000`

## 🔒 Security Note

Never commit your `.env` file to version control. Keep your credentials secure!
