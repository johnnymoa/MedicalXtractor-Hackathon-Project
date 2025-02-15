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
        print("\n🔍 Starting document analysis...")
        all_extractions = []
        
        for category_name, category in self.template.items():
            # Skip categories that aren't version 1.0
            if category.get('version') != '1.0':
                continue
                
            print(f"\n📑 Processing category: {category_name}")
            fields_description = "\n".join([
                f"- {field['Field']}: {field['Description']} (Example: {field['Example']})"
                for field in category['fields']
            ])
            print("\n📋 Fields to extract:")
            print(fields_description)
            print(f"🔎 Analyzing {len(category['fields'])} fields in {category_name}")
            
            # Create a set of valid fields for this category
            valid_fields = {field['Field'] for field in category['fields']}
            
            prompt = f"""Analyze this medical document and extract information according to these fields:
Only extract information for these specific fields. Do not extract any additional fields or information beyond what is listed here:
For each field, I will only extract information that matches EXACTLY these field names:
{fields_description}

DO NOT create or invent any field names that are not in the list above. Only use the exact field names provided.

For example, if looking for "Full Name" field, do not output "Patient Name" or "Name" - it must be exactly "Full Name".

The field names must match PRECISELY what is specified in the template, including capitalization.


IMPORTANT INSTRUCTIONS:
- Only extract information that is EXPLICITLY present in the document. Do not make assumptions or hallucinate values.
- It's perfectly acceptable to not find all fields - only return fields you find with high confidence.
- For 'associated_date', only include if you find an actual date in the document related to the exam, procedure, or document creation.
- If you're unsure about a value, it's better to not include it than to guess.

Document content:
{text}

For each piece of information you find, determine which page it appears on from this page information:
{json.dumps(pages_info, indent=2)}

Return ONLY a JSON array using this structure:
[
    {{
        "field": "Field Name",
        "value": "Extracted Value",
        "page_number": page_number,
        "associated_date": "YYYY-MM-DD" // only if a relevant date is found in the document
    }}
]"""

            try:
                print(f"🤖 Sending request to Mistral AI for {category_name}...")
                response = self.mistral_client.chat.complete(
                    model="mistral-large-latest",
                    messages=[
                        {"role": "system", "content": "You are a medical document analyzer. Extract structured information from medical documents."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    top_p=0.1,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                print(f"✅ Received response for {category_name}")
                print(f"📝 Raw response: {content[:200]}...")  # Print first 200 chars of response
                
                try:
                    findings = json.loads(content)
                    print(f"✨ Successfully parsed JSON for {category_name}")
                    print(f"🔍 Raw findings structure: {json.dumps(findings, indent=2)}")  # Added debug
                    
                    if not isinstance(findings, list):
                        print(f"❌ Expected findings to be a list, got {type(findings)}")
                        continue
                        
                    print(f"📊 Found {len(findings)} findings for {category_name}")
                    for finding in findings:
                        print(f"🔎 Processing finding: {json.dumps(finding, indent=2)}")  # Added debug
                        
                        if not finding.get('value'):
                            print(f"⚠️ Skipping finding without value: {finding}")
                            continue
                            
                        # Validate that the field exists in the template for this category
                        field_name = finding.get('field')
                        if field_name not in valid_fields:
                            print(f"⚠️ Skipping invalid field '{field_name}' for category '{category_name}'")
                            continue
                            
                        value = finding['value']
                        # Handle both string and list/dict values
                        if isinstance(value, (list, dict)):
                            processed_value = json.dumps(value)  # Convert lists/dicts to JSON string
                        else:
                            processed_value = value.strip() if isinstance(value, str) else str(value)
                        
                        print(f"   🏷️  Field: {field_name}")
                        print(f"   📄 Value: {processed_value}")
                        print(f"   📃 Page: {finding.get('page_number', 1)}")

                        # Parse and validate dates
                        associated_date = None
                        try:
                            if finding.get('associated_date'):
                                associated_date = dateutil.parser.parse(finding['associated_date']).strftime("%Y-%m-%d")
                                print(f"   📅 Date: {associated_date}")
                        except (ValueError, TypeError) as e:
                            print(f"   ⚠️  Invalid date format: {finding.get('associated_date')}")
                            print(f"   ⚠️  Date error details: {str(e)}")
                            pass

                        extraction = {
                            'category': category_name,
                            'field': field_name,
                            'value': processed_value,
                            'page_number': finding.get('page_number', 1),
                            'associated_date': associated_date,
                            'extraction_date': datetime.utcnow().isoformat()
                        }
                        print(f"   ✅ Created extraction: {json.dumps(extraction, indent=2)}")
                        all_extractions.append(extraction)
                except json.JSONDecodeError as je:
                    print(f"❌ Error decoding JSON for category {category_name}: {str(je)}")
                    print(f"❌ Raw content causing error: {content}")
                    continue
                        
            except Exception as e:
                print(f"❌ Error processing category {category_name}: {str(e)}")
                print(f"❌ Error type: {type(e).__name__}")
                print(f"❌ Full error details: {str(e)}")
                continue
                
        print(f"\n✅ Analysis complete! Extracted {len(all_extractions)} total items across all categories")
        print(f"📦 Final extractions: {json.dumps(all_extractions, indent=2)}")  # Added debug
        return all_extractions

def process_document_summary(document_pages: List[Dict[str, str]], mistral_client) -> Dict[str, Any]:
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
        
        # Combine all pages content with page markers
        full_text = "\n".join([
            f"<START PAGE {page['page_number']}>\n{page['content']}\n<END PAGE {page['page_number']}>"
            for page in document_pages
        ])
        
        # Process with summarizer agent
        extractions = agent.analyze_document(full_text, pages_info)
        
        return {
            'extractions': extractions,
            'extraction_date': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {'error': f"Error in process_document_summary: {str(e)}"} 