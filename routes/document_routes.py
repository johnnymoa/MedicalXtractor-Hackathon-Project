from flask import jsonify, request, send_file
from io import BytesIO
import base64
from datetime import datetime
import dateutil.parser
from flask_login import current_user
from models import Patient

def init_document_routes(app, db, Document, Page, process_pdf_document, mistral_client):
    @app.route('/api/documents', methods=['GET'])
    def get_documents():
        """Get all documents with role-based filtering"""
        try:
            query = Document.query
            
            if current_user.role == 'medecin':
                patient_id = request.args.get('patient_id')
                if not patient_id:
                    return jsonify([])
                patient = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
                if not patient:
                    return jsonify([])
                query = query.filter_by(user_id=patient.user_id)
            elif current_user.role == 'patient':
                query = query.filter_by(user_id=current_user.id)
                
            documents = query.order_by(Document.upload_date.desc()).all()
            return jsonify([{
                'id': doc.id,
                'filename': doc.filename,
                'upload_date': doc.upload_date.isoformat(),
                'total_pages': doc.total_pages
            } for doc in documents])
        except Exception as e:
            return jsonify({'error': str(e)}), 500

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
                return jsonify({'status': 'error', 'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'status': 'error', 'error': 'No file selected'}), 400
            
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({'status': 'error', 'error': 'File must be a PDF'}), 400

            # Vérifier le patient_id pour les médecins
            if current_user.role == 'medecin':
                patient_id = request.form.get('patient_id')
                if not patient_id:
                    return jsonify({'status': 'error', 'error': 'Patient ID is required'}), 400
                    
                # Vérifier que le patient appartient bien au médecin
                patient = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
                if not patient:
                    return jsonify({'status': 'error', 'error': 'Invalid patient ID'}), 403
                    
                user_id = patient.user_id
            else:
                user_id = current_user.id

            result = process_pdf_document(file, db, Document, Page, mistral_client, user_id)
            
            if result.get('status') == 'error':
                return jsonify(result), 500
                
            return jsonify(result), 200

        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

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