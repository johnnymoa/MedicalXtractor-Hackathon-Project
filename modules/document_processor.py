from flask import jsonify
import tempfile
import os
import fitz  # PyMuPDF
from PIL import Image
import base64
import io
import time
from threading import Semaphore
from mistralai import Mistral

# Rate limiting configuration
MAX_CONCURRENT_CALLS = 2
CALL_DELAY = 1.0
semaphore = Semaphore(MAX_CONCURRENT_CALLS)

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

def process_page_image_with_throttle(image, page_num, mistral_client):
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

def process_pdf_document(file, db, Document, Page, mistral_client):
    """Process a PDF document and store results in the database"""
    try:
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
                    processed_content = process_page_image_with_throttle(image, page_num, mistral_client)
                    
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
            
            return {
                'status': 'success',
                'document_id': document.id,
                'total_pages': len(images),
                'results': results
            }

    except Exception as e:
        db.session.rollback()
        raise e 