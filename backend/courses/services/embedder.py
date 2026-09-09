"""Turn chunk text into embeddings (vectors) using Google Gemini.

We call Gemini through its OpenAI-compatible API, so we keep the same `openai`
client, just pointed at Gemini's base URL with Gemini model names.
"""

from django.conf import settings
from openai import OpenAI


EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 1536   # must match Embedding.embedding VectorField(1536)

# How many texts to send in one request.
EMBED_BATCH_SIZE = 100


class EmbeddingError(Exception):
    """Raised when we cannot produce embeddings (missing key, network, wrong size)."""
    pass


def _client() -> OpenAI:
    if not settings.GEMINI_API_KEY:
        raise EmbeddingError("GEMINI_API_KEY is not set")
    return OpenAI(api_key=settings.GEMINI_API_KEY, base_url=settings.GEMINI_BASE_URL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Turn a list of texts into 1536-dim embedding vectors, in safe batches.

    Raises:
        EmbeddingError: if the key is missing, a request fails, or a vector
            comes back the wrong size.
    """
    if not texts:
        return []

    client = _client()
    vectors: list[list[float]] = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start:start + EMBED_BATCH_SIZE]
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
                dimensions=EMBEDDING_DIMENSIONS,   # Gemini defaults to 3072; force 1536
            )
        except Exception as error:
            raise EmbeddingError(f"Gemini embedding request failed: {error}")

        # response.data comes back in the SAME order as the input batch.
        for item in response.data:
            vectors.append(item.embedding)

    # Every vector must be the right length, or the VectorField(1536) insert
    # will later fail with a confusing error.
    for vector in vectors:
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise EmbeddingError(
                f"Expected {EMBEDDING_DIMENSIONS}-dim vectors, got {len(vector)}"
            )

    return vectors


def embed_text(text: str) -> list[float]:
    """Embed a single text. Used for the student's question at query time."""
    return embed_texts([text])[0]
