from pathlib import Path


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".html", ".pptx", ".docx"}


def parse_document(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(file_path)
    elif ext == ".txt":
        return _parse_txt(file_path)
    elif ext == ".html":
        return _parse_html(file_path)
    elif ext == ".pptx":
        return _parse_pptx(file_path)
    elif ext == ".docx":
        return _parse_docx(file_path)
    raise ValueError(f"Unsupported file type: {ext}")


def _parse_pdf(file_path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _parse_txt(file_path: str) -> str:
    with open(file_path) as f:
        return f.read()


def _parse_html(file_path: str) -> str:
    from bs4 import BeautifulSoup
    with open(file_path) as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    return soup.get_text(separator="\n")


def _parse_pptx(file_path: str) -> str:
    from pptx import Presentation
    prs = Presentation(file_path)
    texts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                texts.append(shape.text)
    return "\n".join(texts)


def _parse_docx(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs)
