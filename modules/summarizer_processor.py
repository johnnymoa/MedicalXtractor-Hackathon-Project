import json
from datetime import datetime
import dateutil.parser
from typing import List, Dict, Any, Optional

class SummarizerAgent:
    def __init__(self, mistral_client):
        self.mistral_client = mistral_client
        self.template = self._load_template()
    
    def _load_template(self) -> List[Dict[str, Any]]:
        with open('modules/SeekerTemplate.json', 'r') as f:
            return json.load(f)
    
    def analyze_document(self, text: str, pages_info: list) -> List[Dict[str, Any]]:
        """Analyze document text and extract structured information based on template"""
        all_extractions = []
        
        for category in self.template:
            category_name = category['category']
            fields_description = "\n".join([
                f"- {field['Field']}: {field['Description']} (Example: {field['Example']})"
                for field in category['fields']
            ])
            
            prompt = f"""Analyze this medical document and extract information according to these fields:

{fields_description}

Document content:
{text}

For each piece of information you find, determine which page it appears on from this page information:
{json.dumps(pages_info, indent=2)}

Return ONLY a JSON array using this structure:
[
    {{
        "field": "Field Name",
        "value": "Extracted Value",
        "page": page_number,
        "associated_date": "YYYY-MM-DD" // if applicable
    }}
]"""

            try:
                response = self.mistral_client.chat.create(
                    model="mistral-large",
                    messages=[
                        {"role": "system", "content": "You are a medical document analyzer. Extract structured information from medical documents."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    top_p=0.1
                )
                
                content = response.choices[0].message.content
                try:
                    findings = json.loads(content)
                    if isinstance(findings, list):
                        for finding in findings:
                            if finding.get('value') and finding.get('value').strip():
                                all_extractions.append({
                                    'category': category_name,
                                    'field': finding['field'],
                                    'value': finding['value'],
                                    'page': finding.get('page', 1),
                                    'associated_date': finding.get('associated_date'),
                                    'extraction_date': datetime.utcnow().isoformat()
                                })
                except json.JSONDecodeError as je:
                    print(f"Error decoding JSON for category {category_name}: {str(je)}")
                    print(f"Raw content: {content}")
                    continue
                        
            except Exception as e:
                print(f"Error processing category {category_name}: {str(e)}")
                continue
                
        return all_extractions

def process_document_summary(document_pages: List[Dict[str, str]], mistral_client) -> List[Dict[str, Any]]:
    """Process a document and extract medical information based on the template."""
    try:
        agent = SummarizerAgent(mistral_client)
        
        # Prepare pages info
        pages_info = [
            {
                'page_number': page['page_number'],
                'content': page['content']
            } for page in document_pages
        ]
        
        # Combine all pages content
        full_text = "\n".join([page['content'] for page in document_pages])
        
        # Process with summarizer agent
        return agent.analyze_document(full_text, pages_info)
    except Exception as e:
        print(f"Error in process_document_summary: {str(e)}")
        return [] 