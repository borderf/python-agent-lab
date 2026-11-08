"""Keep PDF page locations attached to extracted text before importing it."""
from pathlib import Path

from pypdf import PdfReader


def extract_pages(path: Path) -> list[tuple[str, str]]:
    if path.suffix.lower() == ".txt":
        pages = [("正文", path.read_text(encoding="utf-8-sig"))]
    elif path.suffix.lower() == ".pdf":
        pages = [(f"PDF 第 {index} 页", page.extract_text() or "")
                 for index, page in enumerate(PdfReader(path).pages, 1)]
    else:
        raise ValueError("Use a UTF-8 text file or a text-based PDF")
    if not pages:
        raise ValueError("Document has no pages")
    for section, text in pages:
        if not text.strip():
            raise ValueError(f"{section}: no text; inspect the page or prepare OCR separately")
    return [(section, text.strip()) for section, text in pages]
