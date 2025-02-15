from flask import jsonify

def init_prescription_routes(app, db, Document, PrescriptionAnalysis, Medication, PrescriptionAgent, process_prescription_analysis, mistral_client):
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
                        'duration_raw': med.duration_raw,
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
                        'duration_raw': med.duration_raw,
                        'end_date': med.end_date.isoformat() if med.end_date else None,
                        'instructions': med.instructions,
                        'page_number': med.page_number
                    } for med in document.prescription.medications]
                })
            
            prescription_agent = PrescriptionAgent(mistral_client)
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