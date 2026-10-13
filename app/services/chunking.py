def split_words(text: str, size: int = 200, overlap: int = 30) -> list[str]:
    words = text.split()
    step = size - overlap
    pieces = []
    for start in range(0, len(words), step):
        pieces.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
    return pieces


def chunk_segments(segments: list[dict], size: int = 200, overlap: int = 30) -> list[dict]:
    chunks = []
    for seg in segments:  # har segment = ek page ya ek section, isliye page cross nahi hota
        for piece in split_words(seg["text"], size, overlap):
            chunks.append({
                "page": seg["page"],
                "section": seg["section"],
                "text": piece,
                "chunk_index": len(chunks),
            })
    return chunks