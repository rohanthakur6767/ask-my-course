
#We chunk PAGE BY PAGE, so every chunk keeps the exact page number it came from.
from dataclasses import dataclass
import re
from courses.services.pdf_extractor import PageText


DEFAULT_CHUNK_SIZE_WORDS = 400
DEFAULT_CHUNK_OVERLAP_WORDS = 60


@dataclass
class Chunk:
    """One piece of a material, ready to be embedded."""
    text: str          # the chunk's text
    chunk_index: int   # 0, 1, 2... order across the whole material
    page_number: int   # which page this chunk came from


def _count_words(text: str) -> int:
    return len(text.split())


def _split_sentences(text: str) -> list[str]: # We split into sentences to preserve meaning
    flattened = text.replace("\n", " ")         # This replaces line breaks with spaces.
    sentences = re.split(r"(?<=[.!?])\s+", flattened) # Split whenever ., !, or ?
    return [s.strip() for s in sentences if s.strip()]


def _overlap_tail(sentences: list[str], overlap_words: int) -> list[str]:
    tail: list[str] = [] # Store the sentences that will overlap into the next chunk.
    total = 0 # Keep track of how many overlap words we have selected.
    for sentence in reversed(sentences): # Start from the last sentence because we want the end of the chunk.
        words = _count_words(sentence)
        if total + words > overlap_words:
            break
        tail.insert(0, sentence)   # insert at front to keep the original order
        total += words
    return tail


def _chunk_one_page(text: str, size_words: int, overlap_words: int) -> list[str]:
    sentences = _split_sentences(text) # Split the page into sentences so we don't cut sentences in half.

    chunks: list[str] = []
    current: list[str] = []   # the sentences in the chunk we are building
    current_words = 0

    for sentence in sentences:
        words = _count_words(sentence)

        if current and current_words + words > size_words:
            chunks.append(" ".join(current)) # Save the current chunk because adding this sentence would exceed the size.
            current = _overlap_tail(current, overlap_words) # Start the next chunk with some sentences from the previous chunk.
            current_words = _count_words(" ".join(current))

        current.append(sentence) # Add the current sentence to the new chunk.
        current_words += words

    # Do not forget the last chunk still sitting in the buffer.
    if current:
        chunks.append(" ".join(current))

    return chunks


def chunk_pages(
    pages: list[PageText],
    size_words: int = DEFAULT_CHUNK_SIZE_WORDS,
    overlap_words: int = DEFAULT_CHUNK_OVERLAP_WORDS,
) -> list[Chunk]:

    # Make sure the chunk size is greater than 0.
    if size_words <= 0:
        raise ValueError("size_words must be greater than 0")

    # Make sure the overlap is smaller than the chunk size.
    if overlap_words >= size_words:
        raise ValueError("overlap_words must be smaller than size_words")

    chunks: list[Chunk] = []     # Store all chunks from all pages.

    index = 0

    for page in pages:
        for chunk_text in _chunk_one_page(page.text, size_words, overlap_words):
            chunks.append(
                Chunk(text=chunk_text, chunk_index=index, page_number=page.page_number)
            )
            index += 1

    return chunks