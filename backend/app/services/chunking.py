import re
from typing import List, Dict, Any, Optional
from app.config import settings
from app.services.extraction import ExtractedPage


class ChunkItem:
    def __init__(
        self,
        chunk_index: int,
        page_number: Optional[int],
        content: str,
        token_count: int,
    ):
        self.chunk_index = chunk_index
        self.page_number = page_number
        self.content = content
        self.token_count = token_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "content": self.content,
            "token_count": self.token_count,
        }


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 characters per token."""
    return max(1, len(text) // 4)


def split_text_recursively(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: Optional[List[str]] = None,
) -> List[str]:
    """
    Splits text recursively using hierarchical separators until chunks fit within chunk_size.
    """
    if separators is None:
        separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    text = text.strip()
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    # Find the first separator present in the text
    chosen_sep = ""
    for sep in separators:
        if sep == "":
            chosen_sep = ""
            break
        if sep in text:
            chosen_sep = sep
            break

    splits: List[str]
    if chosen_sep != "":
        splits = text.split(chosen_sep)
    else:
        splits = list(text)

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for piece in splits:
        piece_len = len(piece) + (len(chosen_sep) if current_chunk else 0)
        if current_length + piece_len <= chunk_size:
            current_chunk.append(piece)
            current_length += piece_len
        else:
            if current_chunk:
                combined = chosen_sep.join(current_chunk).strip()
                if combined:
                    chunks.append(combined)

                # Keep trailing pieces for overlap
                overlap_chunk: List[str] = []
                overlap_len = 0
                for back_piece in reversed(current_chunk):
                    if overlap_len + len(back_piece) <= chunk_overlap:
                        overlap_chunk.insert(0, back_piece)
                        overlap_len += len(back_piece) + len(chosen_sep)
                    else:
                        break
                current_chunk = overlap_chunk
                current_length = sum(len(p) for p in current_chunk) + (
                    len(chosen_sep) * max(0, len(current_chunk) - 1)
                )

            # If the piece itself is larger than chunk_size, split it with remaining separators
            if len(piece) > chunk_size:
                sub_seps = separators[separators.index(chosen_sep) + 1 :] if chosen_sep in separators else [""]
                sub_chunks = split_text_recursively(piece, chunk_size, chunk_overlap, sub_seps)
                chunks.extend(sub_chunks)
            else:
                current_chunk.append(piece)
                current_length += len(piece) + (len(chosen_sep) if len(current_chunk) > 1 else 0)

    if current_chunk:
        combined = chosen_sep.join(current_chunk).strip()
        if combined and (not chunks or chunks[-1] != combined):
            chunks.append(combined)

    return [c for c in chunks if c.strip()]


def chunk_extracted_pages(
    pages: List[ExtractedPage],
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[ChunkItem]:
    """
    Processes extracted pages into numbered, sized, overlapping chunks preserving page metadata.
    """
    size = chunk_size or settings.CHUNK_SIZE
    overlap = chunk_overlap or settings.CHUNK_OVERLAP

    all_chunks: List[ChunkItem] = []
    global_index = 0

    for page in pages:
        page_chunks = split_text_recursively(page.content, size, overlap)
        for chunk_text in page_chunks:
            all_chunks.append(
                ChunkItem(
                    chunk_index=global_index,
                    page_number=page.page_number,
                    content=chunk_text,
                    token_count=estimate_tokens(chunk_text),
                )
            )
            global_index += 1

    return all_chunks
