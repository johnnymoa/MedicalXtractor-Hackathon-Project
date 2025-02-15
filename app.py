from flask import Flask, request, jsonify, send_from_directory, send_file, render_template, url_for
from flask_cors import CORS
from mistralai import Mistral
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from modules.document_processor import process_pdf_document
from modules.prescription_processor import PrescriptionAgent, process_prescription_analysis
from modules.summarizer_processor import process_document_summary
import json
import tempfile
import io
from PIL import Image
import base64
import fitz  # PyMuPDF
from concurrent.futures import ThreadPoolExecutor
import time
from threading import Semaphore
import dateutil.parser
import base64
from io import BytesIO

# Import route modules
from routes.document_routes import init_document_routes
from routes.prescription_routes import init_prescription_routes
from routes.summary_routes import init_summary_routes

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, 
    static_url_path='/static',
    template_folder='templates'  # Explicitly set the template folder
)
CORS(app)

# Increase timeout to 10 minutes
app.config['TIMEOUT'] = 3600  # 1 hour timeout in seconds

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] =  os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Document model
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    total_pages = db.Column(db.Integer, nullable=False)
    pages = db.relationship('Page', backref='document', lazy=True, cascade='all, delete-orphan')
    prescription = db.relationship('PrescriptionAnalysis', backref='document', lazy=True, uselist=False, cascade='all, delete-orphan')
    summary = db.relationship('DocumentSummary', backref='document', lazy=True, uselist=False, cascade='all, delete-orphan')

class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page_number = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_data = db.Column(db.Text)  # Store base64 encoded image
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)

class PrescriptionAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    analysis_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    medications = db.relationship('Medication', backref='prescription', lazy=True, cascade='all, delete-orphan')

class Medication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescription_analysis.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    dosage = db.Column(db.String(255))
    frequency = db.Column(db.String(255))
    start_date = db.Column(db.Date)
    duration = db.Column(db.String(255))
    duration_raw = db.Column(db.String(255))
    end_date = db.Column(db.Date)
    instructions = db.Column(db.Text)
    page_number = db.Column(db.Integer)

class DocumentSummary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    analysis_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    extractions = db.relationship('SummaryExtraction', backref='summary', lazy=True, cascade='all, delete-orphan')

class SummaryExtraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    summary_id = db.Column(db.Integer, db.ForeignKey('document_summary.id'), nullable=False)
    category = db.Column(db.String(255), nullable=False)
    field = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text, nullable=False)
    page_number = db.Column(db.Integer)
    associated_date = db.Column(db.Date)
    extraction_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# Mistral client configuration
mistral_api_key = os.getenv("MISTRAL_API_KEY")
mistral_client = Mistral(api_key=mistral_api_key)

# Create database tables
with app.app_context():
    db.create_all()

# Initialize routes
init_document_routes(app, db, Document, Page, process_pdf_document, mistral_client)
init_prescription_routes(app, db, Document, PrescriptionAnalysis, Medication, PrescriptionAgent, process_prescription_analysis, mistral_client)
init_summary_routes(app, db, Document, DocumentSummary, SummaryExtraction, process_document_summary, mistral_client)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/documents')
def documents():
    return render_template('documents.html')

@app.route('/prescriptions')
def prescriptions():
    return render_template('prescriptions.html')

@app.route('/summarizer')
def summarizer():
    return render_template('summarizer.html')

@app.route('/credits')
def credits():
    return render_template('credits.html')

if __name__ == '__main__':
    app.run(debug=True, port=8080)
