import os
from PyPDF2 import PdfReader, PdfWriter

def split_pdf(input_path, num_parts=10):
    """
    Splits the PDF file located at input_path into num_parts smaller PDFs.
    
    Args:
        input_path (str): The path to the original PDF file.
        num_parts (int): The number of parts to split the PDF into (default is 10).
    
    This function reads the input PDF, calculates how many pages should go in each part
    (distributing extra pages evenly among the first parts), and saves each part as a new PDF file
    in the same directory as the input file.
    """
    # Read the PDF file
    pdf = PdfReader(input_path)
    total_pages = len(pdf.pages)
    
    # Calculate the base number of pages per part and the number of extra pages to distribute
    pages_per_part = total_pages // num_parts
    remaining_pages = total_pages % num_parts
    
    # Determine the output directory from the input path
    output_dir = os.path.dirname(input_path)
    
    # Begin splitting the PDF by tracking the starting page
    start_page = 0
    for i in range(num_parts):
        # Create a new PDF writer for the current split part
        pdf_writer = PdfWriter()
        
        # Determine the number of pages for this part,
        # adding one extra page if there are remaining pages to distribute
        pages_this_part = pages_per_part + (1 if i < remaining_pages else 0)
        end_page = start_page + pages_this_part
        
        # Add pages from the original PDF to the current writer
        for page_num in range(start_page, min(end_page, total_pages)):
            pdf_writer.add_page(pdf.pages[page_num])
        
        # Construct the output filename and path for the current part
        output_filename = f"medical_document_part_{i+1}.pdf"
        output_path = os.path.join(output_dir, output_filename)
        
        # Write the current part to a new PDF file
        with open(output_path, "wb") as output_file:
            pdf_writer.write(output_file)
        
        print(f"Created {output_filename}")
        
        # Update the start_page for the next iteration
        start_page = end_page
if __name__ == "__main__":
    input_file = "medical document.pdf"
    if not os.path.exists(input_file):
        print(f"Error: Could not find {input_file}")
        exit(1)
        
    print("Starting to split PDF...")
    split_pdf(input_file)
    print("PDF splitting completed!") 