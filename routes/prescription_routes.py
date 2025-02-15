from flask import jsonify, request
from flask_login import login_required, current_user
from models import Patient

def init_prescription_routes(app, db, Document, PrescriptionAnalysis, Medication, prescription_agent, process_prescription_analysis, mistral_client):
    @app.route('/api/analyze-prescription/<int:doc_id>', methods=['GET'])
    @login_required
    def get_prescription_analysis(doc_id):
        """Get prescription analysis for a document if it exists"""
        try:
            document = Document.query.get_or_404(doc_id)
            
            # Verify permissions
            if current_user.role == 'medecin':
                patient_id = request.args.get('patient_id')
                if not patient_id:
                    return jsonify({'error': 'Patient ID is required'}), 400
                patient = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
                if not patient or document.user_id != patient.user_id:
                    return jsonify({'error': 'Access denied'}), 403
            elif current_user.role == 'patient' and document.user_id != current_user.id:
                return jsonify({'error': 'Access denied'}), 403
            
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
    @login_required
    def analyze_prescription(doc_id):
        """Analyze prescription document and create structured data"""
        try:
            document = Document.query.get_or_404(doc_id)
            
            # Verify permissions
            if current_user.role == 'medecin':
                patient_id = request.args.get('patient_id')
                if not patient_id:
                    return jsonify({'error': 'Patient ID is required'}), 400
                patient = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
                if not patient or document.user_id != patient.user_id:
                    return jsonify({'error': 'Access denied'}), 403
            elif current_user.role == 'patient' and document.user_id != current_user.id:
                return jsonify({'error': 'Access denied'}), 403
            
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
    @login_required
    def delete_prescription_analysis(doc_id):
        """Delete prescription analysis for a document"""
        try:
            document = Document.query.get_or_404(doc_id)
            
            # Verify permissions
            if current_user.role == 'medecin':
                patient_id = request.args.get('patient_id')
                if not patient_id:
                    return jsonify({'error': 'Patient ID is required'}), 400
                patient = Patient.query.filter_by(id=patient_id, doctor_id=current_user.id).first()
                if not patient or document.user_id != patient.user_id:
                    return jsonify({'error': 'Access denied'}), 403
            elif current_user.role == 'patient' and document.user_id != current_user.id:
                return jsonify({'error': 'Access denied'}), 403
            
            if document.prescription:
                db.session.delete(document.prescription)
                db.session.commit()
                return jsonify({'message': 'Prescription analysis deleted successfully'})
            return jsonify({'message': 'No prescription analysis found'}), 404
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f"Error deleting prescription analysis: {str(e)}"}), 500 