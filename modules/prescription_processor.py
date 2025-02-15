from mistralai import Mistral
from datetime import datetime, timedelta
import json
import dateutil.parser
from flask_sqlalchemy import SQLAlchemy
from typing import Optional

def compute_prescription_end_date(start_date: str, duration: str) -> Optional[str]:
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

class PrescriptionAgent:
    def __init__(self, mistral_client: Mistral):
        self.mistral_client = mistral_client
        
    def analyze_prescription(self, text: str, pages_info: list) -> dict:
        """Analyze prescription text and extract structured information"""
        try:
            messages = [
                {"role": "system", "content": "You are a medical prescription analyzer. Extract structured information from prescriptions."},
                {"role": "user", "content": f"""Analyze this prescription and return ONLY a JSON object with this exact structure:
                {{
                    "medications": [
                        {{
                            "name": "medication name",
                            "dosage": "dosage information",
                            "frequency": "how often to take",
                            "start_date": "YYYY-MM-DD format",
                            "duration": "duration in format: X days/weeks/months",
                            "instructions": "additional instructions",
                            "page_number": "page number where this medication was found (integer)"
                        }}
                    ]
                }}
                
                For each medication you find, determine which page it appears on from this page information:
                {pages_info}
                
                Prescription text:
                {text}"""}
            ]
            
            response = self.mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=messages,
                temperature=0.1,
                top_p=0.1,
                response_format={"type": "json_object"}
            )
            
            initial_data = json.loads(response.choices[0].message.content)
            processed_data = {"medications": []}
            
            for med in initial_data.get("medications", []):
                processed_med = med.copy()
                
                if med.get("start_date") and med.get("duration"):
                    end_date = compute_prescription_end_date(
                        start_date=med["start_date"],
                        duration=med["duration"]
                    )
                    processed_med["end_date"] = end_date
                else:
                    processed_med["end_date"] = None
                
                processed_data["medications"].append(processed_med)
            
            return processed_data
            
        except Exception as e:
            return {"error": f"Error analyzing prescription: {str(e)}"}

def process_prescription_analysis(document, prescription_agent, db, PrescriptionAnalysis, Medication):
    """Process prescription analysis for a document and save to database"""
    try:
        # Check if analysis already exists
        if document.prescription:
            return {
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
            }

        # Prepare pages info for analysis
        pages_info = [
            {
                'page_number': page.page_number,
                'content': page.content
            } for page in document.pages
        ]
        
        # Combine all pages content
        full_text = "\n".join([page.content for page in document.pages])
        
        # Analyze with prescription agent
        analysis_result = prescription_agent.analyze_prescription(full_text, pages_info)
        
        if 'error' in analysis_result:
            return analysis_result
            
        # Create new prescription analysis
        prescription = PrescriptionAnalysis(document=document)
        db.session.add(prescription)
        
        # Add medications
        for med_data in analysis_result.get('medications', []):
            # Parse dates safely
            start_date = None
            end_date = None
            try:
                if med_data.get('start_date'):
                    start_date = dateutil.parser.parse(med_data['start_date']).date()
            except (ValueError, TypeError):
                pass
                
            try:
                if med_data.get('end_date'):
                    end_date = dateutil.parser.parse(med_data['end_date']).date()
            except (ValueError, TypeError):
                pass
            
            medication = Medication(
                prescription=prescription,
                name=med_data['name'],
                dosage=med_data.get('dosage'),
                frequency=med_data.get('frequency'),
                start_date=start_date,
                duration=med_data.get('duration'),
                end_date=end_date,
                instructions=med_data.get('instructions'),
                page_number=med_data.get('page_number')
            )
            db.session.add(medication)
        
        db.session.commit()
        return analysis_result
        
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error processing prescription analysis: {str(e)}") 