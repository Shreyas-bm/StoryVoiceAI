import pypdf
import docx
from io import BytesIO

def parse_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file."""
    try:
        reader = pypdf.PdfReader(BytesIO(file_bytes))
        text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
        return "\n".join(text).strip()
    except Exception as e:
        raise ValueError(f"Failed to parse PDF document: {str(e)}")

def parse_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file."""
    try:
        doc = docx.Document(BytesIO(file_bytes))
        text = []
        for paragraph in doc.paragraphs:
            if paragraph.text:
                text.append(paragraph.text)
        return "\n".join(text).strip()
    except Exception as e:
        raise ValueError(f"Failed to parse Word document (DOCX): {str(e)}")

def parse_txt(file_bytes: bytes) -> str:
    """Extract text from a TXT file."""
    try:
        return file_bytes.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        raise ValueError(f"Failed to parse text document (TXT): {str(e)}")

def parse_document(file_bytes: bytes, filename: str) -> str:
    """Determine file type and parse the document bytes accordingly."""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return parse_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return parse_docx(file_bytes)
    elif ext == "txt":
        return parse_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: {ext or 'unknown'}. Only PDF, DOCX, and TXT are supported.")
