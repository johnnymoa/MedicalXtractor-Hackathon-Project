from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from mistralai import Mistral
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import tempfile
import io
from PIL import Image
import base64
import fitz  # PyMuPDF
import time
from threading import Semaphore
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_url_path='/static')
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///documents.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Rate limiting configuration
MAX_CONCURRENT_CALLS = 2
CALL_DELAY = 1.0
semaphore = Semaphore(MAX_CONCURRENT_CALLS)

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
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)

# Create database tables
with app.app_context():
    db.create_all()

# Mistral client configuration
mistral_api_key = os.getenv("MISTRAL_API_KEY")
mistral_client = Mistral(api_key=mistral_api_key)

def pdf_to_images(pdf_path):
    """Convert PDF pages to images using PyMuPDF"""
    pdf_document = fitz.open(pdf_path)
    images = []
    
    for page_num in range(len(pdf_document)):
        try:
            page = pdf_document[page_num]
            zoom = 2
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            if img.size[0] > 0 and img.size[1] > 0:
                images.append(img)
            else:
                print(f"Warning: Invalid image size for page {page_num + 1}")
                continue
                
        except Exception as e:
            print(f"Error converting page {page_num + 1}: {str(e)}")
            continue
    
    pdf_document.close()
    
    if not images:
        raise ValueError("No valid images could be extracted from the PDF")
    
    return images

def encode_image(image):
    """Encode PIL Image to base64"""
    try:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG', optimize=True, quality=95)
        img_byte_arr.seek(0)
        return base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
    except Exception as e:
        raise ValueError(f"Error encoding image: {str(e)}")

def process_page_image_with_throttle(image, page_num):
    """Process a single page image using Mistral's Pixtral model with rate limiting"""
    with semaphore:
        try:
            base64_image = encode_image(image)
            if not base64_image:
                raise ValueError("Failed to encode image to base64")
            
            response = mistral_client.chat.complete(
                model="pixtral-large-latest",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Extract all text from this image of page {page_num}. Return only the extracted text, no additional commentary."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,
                top_p=0.1
            )
            
            time.sleep(CALL_DELAY)
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error processing page {page_num}: {str(e)}")
            return f"Error processing page {page_num}: {str(e)}"

@app.route('/')
def index():
    return send_from_directory('static', 'documents.html')

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
            'content': page.content
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

        # Create a temporary file to store the PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            file.save(temp_file.name)
            
            # Convert PDF to images
            images = pdf_to_images(temp_file.name)
            
            # Create new document in database
            document = Document(
                filename=file.filename,
                total_pages=len(images)
            )
            db.session.add(document)
            
            # Process images sequentially
            results = []
            for page_num, image in enumerate(images, start=1):
                try:
                    processed_content = process_page_image_with_throttle(image, page_num)
                    
                    # Save page to database
                    page = Page(
                        page_number=page_num,
                        content=processed_content,
                        document=document
                    )
                    db.session.add(page)
                    
                    results.append({
                        'page_number': page_num,
                        'content': processed_content
                    })
                    
                    # Commit each page individually to save progress
                    db.session.commit()
                    
                except Exception as e:
                    print(f"Error processing page {page_num}: {str(e)}")
                    results.append({
                        'page_number': page_num,
                        'content': f"Error processing page {page_num}: {str(e)}"
                    })
            
            # Clean up temporary file
            os.unlink(temp_file.name)
            
            return jsonify({
                'status': 'success',
                'document_id': document.id,
                'total_pages': len(images),
                'results': results
            })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
