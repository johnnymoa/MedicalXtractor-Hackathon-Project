from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from mistralai import Mistral
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from dotenv import load_dotenv
from modules.document_processor import process_pdf_document

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_url_path='/static')
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///documents.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Document model
class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    total_pages = db.Column(db.Integer, nullable=False)
    pages = db.relationship('Page', backref='document', lazy=True, cascade='all, delete-orphan')

class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page_number = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_data = db.Column(db.Text)  # Store base64 encoded image
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)

# Create database tables
with app.app_context():
    db.create_all()

# Mistral client configuration
mistral_api_key = os.getenv("MISTRAL_API_KEY")
mistral_client = Mistral(api_key=mistral_api_key)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

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

if __name__ == '__main__':
    app.run(debug=True, port=5001)
