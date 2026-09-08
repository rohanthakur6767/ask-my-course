"""Turn chunk text into embeddings (vectors) using OpenAI."""

from django.conf import settings
from openai import OpenAI


# These match the model and our Embedding.embedding VectorField(1536).
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# How many texts to send to OpenAI in one request (stay well under its limits).
EMBED_BATCH_SIZE = 100


class EmbeddingError(Exception):
    """Raised when we cannot produce embeddings (missing key, network, wrong size)."""
    pass


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Turn a list of texts into 1536-dim embedding vectors, in safe batches.

    Args:
        texts: the chunk texts to embed.

    Returns:
        One vector per input text, in the same order.

    Raises:
        EmbeddingError: if the key is missing, the request fails, or a vector
            comes back the wrong size.
    """
    if not texts:
        return []

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise EmbeddingError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    vectors: list[list[float]] = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start:start + EMBED_BATCH_SIZE]
        try:
            response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        except Exception as error:
            raise EmbeddingError(f"OpenAI embedding request failed: {error}")

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
