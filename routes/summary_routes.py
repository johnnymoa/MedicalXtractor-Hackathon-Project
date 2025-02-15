from flask import jsonify
import dateutil.parser
import json

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
                        'value': ext.value,  # Send the raw value as stored in the database
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
            print(f"\n🔄 Starting summary analysis for document {doc_id}")
            document = Document.query.get_or_404(doc_id)
            
            # Only create new analysis if one doesn't exist
            if document.summary:
                print(f"📝 Summary already exists for document {doc_id}")
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
            print(f"📄 Retrieved {len(pages)} pages for processing")
            
            # Process document using summarizer
            print("🤖 Starting document processing...")
            result = process_document_summary(pages, mistral_client)
            
            # Check for errors in processing
            if 'error' in result:
                print(f"❌ Error in document processing: {result['error']}")
                raise Exception(result['error'])
                
            extractions = result['extractions']
            print(f"✅ Successfully processed document, got {len(extractions)} extractions")
            
            # Create new summary
            print("💾 Creating new summary record...")
            summary = DocumentSummary(document_id=doc_id)
            db.session.add(summary)
            db.session.flush()  # Flush to get the summary ID
            print(f"✅ Created summary record with ID: {summary.id}")
            
            # Add extractions
            print("📥 Adding extractions to database...")
            for i, ext in enumerate(extractions, 1):
                try:
                    print(f"\n🔄 Processing extraction {i}/{len(extractions)}")
                    print(f"📝 Extraction data: {json.dumps(ext, indent=2)}")
                    
                    # Parse date if present
                    associated_date = None
                    if ext.get('associated_date'):
                        try:
                            associated_date = dateutil.parser.parse(ext['associated_date']).date()
                            print(f"📅 Parsed associated_date: {associated_date}")
                        except Exception as date_error:
                            print(f"⚠️ Error parsing date: {str(date_error)}")
                    
                    extraction = SummaryExtraction(
                        summary_id=summary.id,
                        category=ext['category'],
                        field=ext['field'],
                        value=ext['value'],
                        page_number=ext['page_number'],
                        associated_date=associated_date,
                        extraction_date=dateutil.parser.parse(ext['extraction_date'])
                    )
                    print(f"✅ Created extraction object: {extraction}")
                    db.session.add(extraction)
                    print(f"✅ Added extraction {i} to session")
                except Exception as ext_error:
                    print(f"❌ Error processing extraction {i}: {str(ext_error)}")
                    print(f"❌ Problematic extraction data: {json.dumps(ext, indent=2)}")
                    raise
            
            print("💾 Committing all changes to database...")
            db.session.commit()
            print("✅ Successfully committed all changes")
            
            return jsonify({
                'extractions': extractions
            })
            
        except Exception as e:
            print(f"❌ Error in analyze_document_summary: {str(e)}")
            print(f"❌ Error type: {type(e).__name__}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
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