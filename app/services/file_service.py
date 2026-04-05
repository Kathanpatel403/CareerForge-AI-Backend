import io
from pypdf import PdfReader
from docx import Document
from fastapi import UploadFile

async def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """
    Extracts plain text from PDF or Word (.docx) files.
    """
    text = ""
    try:
        if filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(file_content))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        elif filename.endswith(".docx"):
            doc = Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            # Fallback for plain text or generic
            text = file_content.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Error extracting text from {filename}: {e}")
        return ""
    
    return text.strip()
