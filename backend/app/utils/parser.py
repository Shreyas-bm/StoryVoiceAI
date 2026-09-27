from pathlib import Path
from io import BytesIO
from typing import Callable, Dict
import pypdf
import docx

def parse_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file."""
    try:
        reader = pypdf.PdfReader(BytesIO(file_bytes))
        return "\n".join(filter(None, (page.extract_text() for page in reader.pages))).strip()
    except Exception as e:
        raise ValueError(f"Failed to parse PDF document: {e}")

def parse_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file."""
    try:
        doc = docx.Document(BytesIO(file_bytes))
        return "\n".join(filter(None, (p.text for p in doc.paragraphs))).strip()
    except Exception as e:
        raise ValueError(f"Failed to parse Word document (DOCX): {e}")

def parse_txt(file_bytes: bytes) -> str:
    """Extract text from a TXT file."""
    try:
        return file_bytes.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        raise ValueError(f"Failed to parse text document (TXT): {e}")

PARSERS: Dict[str, Callable[[bytes], str]] = {
    "pdf": parse_pdf,
    "docx": parse_docx,
    "doc": parse_docx,
    "txt": parse_txt,
}

def parse_document(file_bytes: bytes, filename: str) -> str:
    """Determine file type and parse the document bytes accordingly."""
    ext = Path(filename).suffix.lstrip(".").lower()
    parser = PARSERS.get(ext)
    if not parser:
        raise ValueError(f"Unsupported file format: {ext or 'unknown'}. Only PDF, DOCX, and TXT are supported.")
    return parser(file_bytes)

