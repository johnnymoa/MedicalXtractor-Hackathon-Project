from flask import Flask, request, jsonify, send_from_directory, send_file, render_template, url_for
from flask_cors import CORS
from mistralai import Mistral
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from modules.document_processor import process_pdf_document
from modules.prescription_processor import PrescriptionAgent, process_prescription_analysis
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

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, 
    static_url_path='/static',
    template_folder='templates'  # Explicitly set the template folder
)
CORS(app)

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

# Create database tables
with app.app_context():
    db.create_all()

# Mistral client configuration
mistral_api_key = os.getenv("MISTRAL_API_KEY")
mistral_client = Mistral(api_key=mistral_api_key)

def compute_prescription_end_date(start_date: str, duration: str) -> str:
    """Compute the end date of a prescription based on start date and duration."""
    try:
        start = dateutil.parser.parse(start_date)
        duration_parts = duration.lower().split()
        if len(duration_parts) != 2:
            return None
            
        amount = int(duration_parts[0])
        unit = duration_parts[1]
        
        if 'month' in unit:
            month = start.month + amount
            year = start.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            end_date = start.replace(year=year, month=month)
        elif 'week' in unit:
            end_date = start + timedelta(weeks=amount)
        elif 'day' in unit:
            end_date = start + timedelta(days=amount)
        else:
            return None
            
        return end_date.strftime("%Y-%m-%d")
    except Exception:
        return None

# Initialize prescription agent
prescription_agent = PrescriptionAgent(mistral_client)

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

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Get all documents"""
    documents = Document.query.all()
    return jsonify([{
        'id': doc.id,
        'filename': doc.filename,
        'upload_date': doc.upload_date.isoformat(),
        'total_pages': doc.total_pages
    } for doc in documents])

@app.route('/api/documents/<int:doc_id>', methods=['GET'])
def get_document(doc_id):
    """Get a specific document with its pages"""
    document = Document.query.get_or_404(doc_id)
    return jsonify({
        'id': document.id,
        'filename': document.filename,
        'upload_date': document.upload_date.isoformat(),
        'total_pages': document.total_pages,
        'pages': [{
            'page_number': page.page_number,
            'content': page.content,
            'image_data': page.image_data
        } for page in document.pages]
    })

@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """Delete a document"""
    document = Document.query.get_or_404(doc_id)
    db.session.delete(document)
    db.session.commit()
    return jsonify({'message': 'Document deleted successfully'})

@app.route('/api/process-pdf', methods=['POST'])
def process_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'File must be a PDF'}), 400

        result = process_pdf_document(file, db, Document, Page, mistral_client)
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-prescription/<int:doc_id>', methods=['GET'])
def get_prescription_analysis(doc_id):
    """Get prescription analysis for a document if it exists"""
    try:
        document = Document.query.get_or_404(doc_id)
        if document.prescription:
            return jsonify({
                'medications': [{
                    'name': med.name,
                    'dosage': med.dosage,
                    'frequency': med.frequency,
                    'start_date': med.start_date.isoformat() if med.start_date else None,
                    'duration': med.duration,
                    'end_date': med.end_date.isoformat() if med.end_date else None,
                    'instructions': med.instructions,
                    'page_number': med.page_number
                } for med in document.prescription.medications]
            })
        return jsonify({'message': 'No prescription analysis found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-prescription/<int:doc_id>', methods=['POST'])
def analyze_prescription(doc_id):
    """Analyze prescription document and create structured data"""
    try:
        document = Document.query.get_or_404(doc_id)
        # Only create new analysis if one doesn't exist
        if document.prescription:
            return jsonify({
                'medications': [{
                    'name': med.name,
                    'dosage': med.dosage,
                    'frequency': med.frequency,
                    'start_date': med.start_date.isoformat() if med.start_date else None,
                    'duration': med.duration,
                    'end_date': med.end_date.isoformat() if med.end_date else None,
                    'instructions': med.instructions,
                    'page_number': med.page_number
                } for med in document.prescription.medications]
            })
        return jsonify(process_prescription_analysis(
            document=document,
            prescription_agent=prescription_agent,
            db=db,
            PrescriptionAnalysis=PrescriptionAnalysis,
            Medication=Medication
        ))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-prescription/<int:doc_id>', methods=['DELETE'])
def delete_prescription_analysis(doc_id):
    """Delete prescription analysis for a document"""
    try:
        document = Document.query.get_or_404(doc_id)
        if document.prescription:
            db.session.delete(document.prescription)
            db.session.commit()
            return jsonify({'message': 'Prescription analysis deleted successfully'})
        return jsonify({'message': 'No prescription analysis found'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Error deleting prescription analysis: {str(e)}"}), 500

@app.route('/api/analyze-summary/<int:doc_id>', methods=['GET'])
def get_document_summary(doc_id):
    """Get summary analysis for a document if it exists"""
    try:
        document = Document.query.get_or_404(doc_id)
        if document.summary:
            return jsonify({
                'extractions': [{
                    'category': ext.category,
                    'field': ext.field,
                    'value': ext.value,
                    'page_number': ext.page_number,
                    'associated_date': ext.associated_date.isoformat() if ext.associated_date else None,
                    'extraction_date': ext.extraction_date.isoformat()
                } for ext in document.summary.extractions]
            })
        return jsonify({'message': 'No summary analysis found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-summary/<int:doc_id>', methods=['POST'])
def analyze_document_summary(doc_id):
    """Analyze document and create structured summary"""
    try:
        document = Document.query.get_or_404(doc_id)
        
        # Only create new analysis if one doesn't exist
        if document.summary:
            return jsonify({
                'extractions': [{
                    'category': ext.category,
                    'field': ext.field,
                    'value': ext.value,
                    'page_number': ext.page_number,
                    'associated_date': ext.associated_date.isoformat() if ext.associated_date else None,
                    'extraction_date': ext.extraction_date.isoformat()
                } for ext in document.summary.extractions]
            })
        
        # Get document pages
        pages = [{
            'page_number': page.page_number,
            'content': page.content
        } for page in document.pages]
        
        # Process document using summarizer
        from modules.summarizer_processor import process_document_summary
        extractions = process_document_summary(pages, mistral_client)
        
        # Create new summary
        summary = DocumentSummary(document_id=doc_id)
        db.session.add(summary)
        
        # Add extractions
        for ext in extractions:
            extraction = SummaryExtraction(
                summary_id=summary.id,
                category=ext['category'],
                field=ext['field'],
                value=ext['value'],
                page_number=ext['page'],
                associated_date=dateutil.parser.parse(ext['associated_date']).date() if ext['associated_date'] else None,
                extraction_date=dateutil.parser.parse(ext['extraction_date'])
            )
            db.session.add(extraction)
        
        db.session.commit()
        
        return jsonify({
            'extractions': extractions
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-summary/<int:doc_id>', methods=['DELETE'])
def delete_document_summary(doc_id):
    """Delete summary analysis for a document"""
    try:
        document = Document.query.get_or_404(doc_id)
        if document.summary:
            db.session.delete(document.summary)
            db.session.commit()
            return jsonify({'message': 'Summary analysis deleted successfully'})
        return jsonify({'message': 'No summary analysis found'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Error deleting summary analysis: {str(e)}"}), 500

@app.route('/api/documents/<int:doc_id>/pages/<int:page_number>/image', methods=['GET'])
def get_page_image(doc_id, page_number):
    """Get the image data for a specific page of a document"""
    try:
        document = Document.query.get_or_404(doc_id)
        page = Page.query.filter_by(document_id=doc_id, page_number=page_number).first_or_404()
        
        if not page.image_data:
            return jsonify({'error': 'No image data available for this page'}), 404
        
        # Extract the base64 image data (remove the data URL prefix if present)
        image_data = page.image_data
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
            
        # Convert base64 to binary
        image_binary = base64.b64decode(image_data)
        
        return send_file(
            BytesIO(image_binary),
            mimetype='image/png',  # Adjust mimetype if needed
            as_attachment=False,
            download_name=f'page_{page_number}.png'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8080)
