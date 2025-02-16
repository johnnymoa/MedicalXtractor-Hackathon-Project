# 🏥 MedicalXtractor (MedXTract) by Team 10x

A web-based application for managing medical documents, prescriptions, and patient information. Built with Python Flask and modern web technologies.

*"Because decoding a medical history shouldn't take longer than a consultation!"* ⚕️🤖

## 📢 Project Manifesto
**Problem**: Doctors (especially young new ones) are drowning in 100+ page medical records (*eagerly awaiting the unified record, AMELI I see you!*).
**Solution**: An AI extractor that transforms Uncle Robert's PDF scans into:
- 🕒 **Prescription Timeline** (active vs expired)
- 🎯 **Structured Medical Summary** (pathologies, allergies, treatments)
- 🔍 **Smart Detection** of critical info.

*"It's like CTRL+F, but Matrix version for busy doctors."* 💊💻

---

## 🚦 Current Status
- [x] MVP coded relentlessly, even after being kicked out on the street at midnight 🥶
- [ ] Deployment at Doctolib (*if they call us back*)
- [ ] "GDPR-compatible" certification (*we added a .env, does that count?*)

---

## Features

- Document management and summarization
- Prescription tracking
- User profile management
- Secure dashboard interface
- Patient records organization

### Component Overview

#### Core Components

1. **Flask Application (app.py)**
   - Main application routing
   - Authentication and authorization
   - Database connections
   - API endpoints

2. **AI Integration (modules/)**
   - Document summarization using Mistral AI
   - Template-based information extraction
   - Natural language processing features

#### Frontend Templates

1. **Dashboard (dashboard.html)**
   - User activity overview
   - Quick access to key features
   - Status notifications

2. **Document Management (documents.html)**
   - File upload and organization
   - Document viewing and sharing
   - Category management

3. **Prescription System (prescriptions.html)**
   - Prescription creation and tracking
   - Medication history
   - Dosage information

4. **Profile Management (edit_profile.html)**
   - User information management
   - Preference settings
   - Security controls

5. **Document Summarization (summarizer.html)**
   - AI-powered document analysis
   - Key information extraction
   - Summary generation

### Technical Stack 🛠️

1. **Backend**
   - Flask (Python web framework) (*the boomer combo* 😎)
   - PostgreSQL (Database)
   - Mistral AI (Document processing) (*thanks to the "pixtral-large" model for OCR 2.0*)

2. **Frontend**
   - Jinja2 (Template engine)
   - Bootstrap (UI framework)
   - JavaScript (Interactive features)

3. **Infrastructure**
   - Email service (SMTP)
   - Document storage
   - Authentication system

### Data Flow

1. **Document Processing**
   ```
   Upload → Storage → AI Processing → Summarization → Display
   ```

2. **User Authentication**
   ```
   Login Request → Validation → Session Creation → Access Grant
   ```

3. **Prescription Management**
   ```
   Creation → Validation → Storage → Notification → Access
   ```

### Security Architecture

1. **Authentication**
   - Session-based authentication
   - Secure password handling
   - Email verification

2. **Data Protection**
   - PostgreSQL secure connections
   - Environment variable protection
   - Encrypted storage

3. **API Security**
   - Rate limiting
   - API key authentication
   - Request validation

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)
- Modern web browser
- MongoDB (for document storage)

## Installation

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

4. Configure the application:
```bash
cp .env.example .env
```

Add the following environment variables to your `.env` file:
```env
# API Keys
MISTRAL_API_KEY=your_mistral_api_key

# Database Configuration
DATABASE_URL=postgresql://username:password@host:port/database

# Security
SECRET_KEY=your_secret_key

# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

> ⚠️ **Important**: Never commit your actual `.env` file to version control. Keep your credentials secure!

## Development Setup

1. Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

2. Run the development server:
```bash
flask run --debug
```

3. Access the application at `http://localhost:5000`

### Development Guidelines

- Follow PEP 8 style guide for Python code
- Use meaningful commit messages
- Write tests for new features
- Update documentation as needed

## API Documentation

The application provides several REST endpoints:

- `GET /api/documents` - Retrieve document list
- `POST /api/documents` - Upload new document
- `GET /api/prescriptions` - Get prescriptions
- `POST /api/summarize` - Summarize document

For detailed API documentation, see `API.md`

## Testing

Run the test suite:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest --cov=app tests/
```

## Deployment

### Production Setup

1. Set production environment variables:
```bash
export FLASK_ENV=production
export FLASK_APP=app.py
```

2. Configure production web server (Gunicorn recommended):
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Docker Deployment

1. Build the Docker image:
```bash
docker build --no-cache --platform=linux/amd64 -t rg.fr-par.scw.cloud/your-namespace-name/your-app-name .
```

2. Push to Scaleway Registry:
```bash
# Push the image to Scaleway Container Registry
docker push rg.fr-par.scw.cloud/your-namespace-name/your-app-name
```

3. Connect to the scalway ssh instance 
```bash
ssh -J bastion@51.159.179.172:61000 root@172.16.0.3
```

4. Pull the container
```bash
docker pull rg.fr-par.scw.cloud/your-namespace-name/your-app-name:latest
```

5. Run the container
```bash
docker run -p 5000:8080 -e DATABASE_URL=sqlite:///app.db -d rg.fr-par.scw.cloud/your-namespace-name/your-app-name:latest 
```

6. Check the container status
```bash
docker ps
```

7. Access the container shell
```bash
docker exec -it xxxxx bash
```

8. Run init_db.py
```bash
python init_db.py
```
## Security

- All routes require authentication
- Documents are encrypted at rest
- HTTPS required for production
- Regular security audits performed
- Rate limiting implemented on API endpoints

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Pull Request Guidelines

- Include tests for new features
- Update documentation
- Follow the existing code style
- One feature per PR

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- GitHub Issues: For bug reports and feature requests

## Acknowledgments

- Flask framework
- Contributors and maintainers

## Environment Variables

The application requires the following environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `MISTRAL_API_KEY` | API key for Mistral AI services | `xxxxxx...` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:port/db` |
| `SECRET_KEY` | Flask secret key for session security | `your-secret-key` |
| `MAIL_SERVER` | SMTP server for email sending | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP server port | `587` |
| `MAIL_USE_TLS` | Enable TLS for email | `True` |
| `MAIL_USERNAME` | Email account username | `your-email@gmail.com` |
| `MAIL_PASSWORD` | Email account password or app password | `your-app-password` |
| `MAIL_DEFAULT_SENDER` | Default sender email address | `your-email@gmail.com` |

## Detailed Application Structure

### Routes & Pages

#### Main Routes
```
├── / (GET)                      # Home page / Landing
├── /login (GET, POST)           # User authentication
├── /dashboard (GET)             # User dashboard
├── /profile (GET, POST)         # Profile management
└── /logout (GET)                # User logout
```

#### Document Management
```
├── /documents (GET)             # Document list
├── /documents/upload (POST)     # Upload new document
├── /documents/<id> (GET)        # View document
├── /documents/<id>/edit (POST)  # Edit document
└── /documents/<id>/delete (POST)# Delete document
```

#### Prescription Management
```
├── /prescriptions (GET)         # Prescription list
├── /prescriptions/new (GET,POST)# Create prescription
├── /prescriptions/<id> (GET)    # View prescription
└── /prescriptions/edit (POST)   # Edit prescription
```

### Templates Structure

```
templates/
├── base.html                    # Base template with common elements
├── dashboard.html               # Dashboard layout and components
│   ├── _activity_feed.html     # Recent activity component
│   └── _quick_actions.html     # Quick action buttons
├── documents.html               # Document management interface
│   ├── _document_list.html     # Document listing component
│   └── _upload_form.html       # Document upload form
├── prescriptions.html           # Prescription management
│   ├── _prescription_form.html # Prescription creation form
│   └── _prescription_list.html # Prescription listing
├── edit_profile.html           # Profile editing interface
│   ├── _personal_info.html     # Personal information form
│   └── _security_settings.html # Security settings
└── summarizer.html             # Document summarization interface
    ├── _summary_result.html    # Summary display component
    └── _upload_section.html    # Document upload for summary
```

### Core Modules

#### SeekerTemplate Module
```json
// modules/SeekerTemplate.json
{
    "document_types": [
        "medical_report",
        "prescription",
        "lab_result",
        "medical_certificate"
    ],
    "extraction_fields": {
        "patient_info": [...],
        "diagnosis": [...],
        "medications": [...],
        "instructions": [...]
    }
}
```

#### Application Features

1. **Document Processing**
   - Document type detection
   - Information extraction
   - Medical terminology recognition
   - Summary generation

2. **User Management**
   - Authentication & authorization
   - Profile customization
   - Activity tracking
   - Notification preferences

3. **Prescription System**
   - Digital prescription creation
   - Medication tracking
   - Dosage calculation
   - Interaction checking

### API Endpoints

#### Document API
```
POST /api/documents
├── Request:
│   ├── file: File (required)
│   └── type: String (optional)
└── Response:
    ├── document_id: String
    └── status: String
```

#### Summarization API
```
POST /api/summarize
├── Request:
│   ├── document_id: String
│   └── options: Object
└── Response:
    ├── summary: String
    └── key_points: Array
```

#### Prescription API
```
POST /api/prescriptions
├── Request:
│   ├── patient_id: String
│   ├── medications: Array
│   └── instructions: String
└── Response:
    ├── prescription_id: String
    └── status: String
```

## Project Structure

### Templates Directory (`/templates`)

#### Authentication Templates (`/templates/auth/`)
```
├── login.html                # User login interface
├── register.html            # New user registration
├── reset_password.html      # Password reset form
└── reset_password_request.html  # Password reset request
```

#### Doctor Interface (`/templates/medecin/`)
```
├── patients.html            # Patient list and management
└── prescriptions.html       # Prescription handling
```

#### Admin Interface (`/templates/admin/`)
```
├── users.html               # User management (English)
└── utilisateurs.html        # User management (French)
```

### Static Files (`/static/`)

#### CSS Files (`/static/css/`)
```
└── toast.css               # Notification styling
```

### Core Application Files

#### Main Application
- `app.py` - Flask application with routes and logic
- `config.py` - Application configuration settings
- `requirements.txt` - Project dependencies

#### Environment Configuration
```env
# API Integration
MISTRAL_API_KEY=            # AI service integration

# Database
DATABASE_URL=               # PostgreSQL connection

# Security
SECRET_KEY=                 # Application security key

# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=
```

### Application Features

#### User Management
- Multi-language support (English/French)
- Role-based access control
  - Admin access
  - Doctor access
  - Patient access

#### Medical Records
- Patient information management
- Prescription tracking
- Document handling

#### Security
- Secure authentication
- Password reset functionality
- Session management

#### Notifications
- Toast notifications
- Email alerts
- System messages

### API Endpoints

#### Authentication
```
├── /auth/login            # User login
├── /auth/register         # User registration
└── /auth/reset-password   # Password reset
```

#### Medical Records
```
├── /medecin/patients      # Patient management
└── /medecin/prescriptions # Prescription handling
```

#### Administration
```
└── /admin/users           # User management
```

### Database Schema

#### Users
- Authentication information
- Role assignments
- Profile data

#### Medical Records
- Patient information
- Prescription data
- Document storage

### Security Implementation

#### Authentication
- Secure password handling
- Email verification
- Session management

#### Data Protection
- Encrypted storage
- Secure communication
- Access control

**Coded with ❤️, 140 dragibus and 20 mini croissants 12 vegan pizza slices by Team10x** 🥤🌭
