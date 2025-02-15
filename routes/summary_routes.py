from flask import jsonify
import dateutil.parser

def init_summary_routes(app, db, Document, DocumentSummary, SummaryExtraction, process_document_summary, mistral_client):
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