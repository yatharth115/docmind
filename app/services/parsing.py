import re
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document as DocxDocument


def clean_text(text: str) -> str:
    text = re.sub(r"-\n(?=[a-z])", "", text)  # line-break wale hyphen jodo
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_pdf(path: str) -> list[dict]:
    with fitz.open(path) as doc:
        raw_pages = [page.get_text() for page in doc]

    pages_lines = [[l.strip() for l in t.splitlines() if l.strip()] for t in raw_pages]

    # header/footer: wo chhoti lines jo 50% se zyada pages pe repeat hoti hain
    repeated = set()
    if len(pages_lines) >= 4:
        counts = Counter(
            line for lines in pages_lines for line in set(lines) if len(line) < 80
        )
        repeated = {line for line, c in counts.items() if c > len(pages_lines) * 0.5}

    segments = []
    for page_no, lines in enumerate(pages_lines, start=1):
        kept = [l for l in lines if l not in repeated]
        text = clean_text("\n".join(kept))
        if text:  # scanned page me text empty hota hai
            segments.append({"page": page_no, "section": None, "text": text})
    return segments


def parse_docx(path: str) -> list[dict]:
    doc = DocxDocument(path)
    segments = []
    current_title = "Introduction"
    buffer: list[str] = []

    def flush():
        if buffer:
            text = clean_text("\n".join(buffer))
            if text:
                segments.append({"page": None, "section": current_title, "text": text})
            buffer.clear()

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = p.style.name if p.style is not None and p.style.name else ""
        if style.startswith("Heading") or style == "Title":
            flush()
            current_title = text[:255]
        else:
            buffer.append(text)
    flush()
    return segments


def parse_file(path: str) -> list[dict]:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix == ".docx":
        return parse_docx(path)
    raise ValueError(f"Unsupported file type: {suffix}")