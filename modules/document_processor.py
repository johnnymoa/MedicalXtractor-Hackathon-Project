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
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from flask_login import current_user

# Rate limiting configuration
MAX_CONCURRENT_CALLS = 3  # Reduced from 5 to 3
CALL_DELAY = 1.0  # Increased from 0.5 to 1.0
MAX_RETRIES = 5
BASE_DELAY = 2
JITTER = 0.1
semaphore = Semaphore(MAX_CONCURRENT_CALLS)

def exponential_backoff(retry_count):
    """Calculate delay with exponential backoff and jitter"""
    delay = min(BASE_DELAY * (2 ** retry_count), 60)  # Cap at 60 seconds
    jitter_amount = delay * JITTER
    return delay + random.uniform(-jitter_amount, jitter_amount)

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
    """Process a single page image using Mistral's Pixtral model with rate limiting and retry logic"""
    with semaphore:
        print(f"[Page {page_num}] Starting processing...")
        start_time = time.time()
        retry_count = 0
        
        while retry_count < MAX_RETRIES:
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
                processing_time = time.time() - start_time
                print(f"[Page {page_num}] Processing completed in {processing_time:.2f} seconds")
                return response.choices[0].message.content
                
            except Exception as e:
                retry_count += 1
                if "429" in str(e) and retry_count < MAX_RETRIES:
                    delay = exponential_backoff(retry_count)
                    print(f"[Page {page_num}] Rate limit hit, retrying in {delay:.2f} seconds (attempt {retry_count}/{MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                else:
                    processing_time = time.time() - start_time
                    error_msg = f"[Page {page_num}] Error after {processing_time:.2f} seconds: {str(e)}"
                    if retry_count >= MAX_RETRIES:
                        error_msg = f"{error_msg} (Max retries reached)"
                    print(error_msg)
                    return f"Error processing page {page_num}: {str(e)}"

def process_pdf_document(file, db, Document, Page, mistral_client):
    """Process a PDF document and store results in the database"""
    temp_file = None
    start_time = time.time()
    print(f"\n[Document] Starting processing of '{file.filename}'...")
    
    try:
        # Create a temporary file to store the PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            file.save(temp_file.name)
            temp_file_path = temp_file.name
            
            # Convert PDF to images
            print("[Document] Converting PDF to images...")
            images = pdf_to_images(temp_file_path)
            
            if not images:
                raise ValueError("No valid pages could be extracted from the PDF")
            
            print(f"[Document] Successfully extracted {len(images)} pages from PDF")
            
            # Create new document in database with user_id
            document = Document(
                filename=file.filename,
                total_pages=len(images),
                user_id=current_user.id  # Add the current user's ID
            )
            db.session.add(document)
            db.session.flush()  # Get the document ID without committing
            
            results = []
            successful_pages = 0
            
            print(f"[Document] Starting page-by-page processing with concurrency...")

            # Use a thread pool to process each page in parallel
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CALLS) as executor:
                # Submit each page processing task to the pool
                future_to_page = {
                    executor.submit(
                        process_page_image_with_throttle,
                        image,
                        page_num,
                        mistral_client
                    ): page_num
                    for page_num, image in enumerate(images, start=1)
                }

                # As each thread completes, store the results
                for future in as_completed(future_to_page):
                    page_num = future_to_page[future]
                    try:
                        processed_content = future.result()
                        if not processed_content:
                            raise ValueError("No content extracted from page")

                        # Encode image to base64
                        base64_image = encode_image(images[page_num - 1])

                        # Save page to database
                        page = Page(
                            page_number=page_num,
                            content=processed_content,
                            image_data=base64_image,
                            document=document
                        )
                        db.session.add(page)
                        db.session.commit()

                        results.append({
                            'page_number': page_num,
                            'content': processed_content,
                            'image_data': base64_image
                        })
                        
                        successful_pages += 1
                        print(f"[Document] Successfully processed and saved page {page_num}/{len(images)}")
                    
                    except Exception as e:
                        db.session.rollback()
                        error_msg = f"Error processing page {page_num}: {str(e)}"
                        print(f"[Document] {error_msg}")
                        results.append({
                            'page_number': page_num,
                            'content': error_msg,
                            'image_data': None
                        })

            if successful_pages == 0:
                raise ValueError("Failed to process any pages successfully")
            
            total_time = time.time() - start_time
            print(f"\n[Document] Completed processing '{file.filename}'")
            print(f"[Document] Total processing time: {total_time:.2f} seconds")
            print(f"[Document] Successfully processed {successful_pages}/{len(images)} pages")
            
            return {
                'status': 'success',
                'document_id': document.id,
                'total_pages': len(images),
                'successful_pages': successful_pages,
                'results': results
            }

    except Exception as e:
        total_time = time.time() - start_time
        db.session.rollback()
        error_message = str(e)
        print(f"\n[Document] Error processing document after {total_time:.2f} seconds")
        print(f"[Document] Error details: {error_message}")
        return {
            'status': 'error',
            'error': error_message
        }
        
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                print("[Document] Cleaned up temporary files")
            except Exception as e:
                print(f"[Document] Error cleaning up temporary file: {str(e)}") 