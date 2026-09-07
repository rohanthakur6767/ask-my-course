import hashlib
import math
import random

from django.conf import settings
from openai import OpenAI


# These match the model and our Embedding.embedding VectorField(1536).
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# How many texts to send to OpenAI in one request.
EMBED_BATCH_SIZE = 100


class EmbeddingError(Exception):
    """Raised when we cannot produce embeddings (bad key, network, wrong size)."""
    pass


def _fake_embedding(text: str) -> list[float]:
    """A deterministic, unit-length fake vector for offline testing."""
    # sha256 gives a STABLE number from the text. We avoid Python's built-in
    # hash(), because it is randomized per run, so the same text would give a
    # different vector each time you restart, which would break testing.
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    vector = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIMENSIONS)]

    # Normalize to length 1, so cosine similarity behaves sensibly.
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / length for value in vector]


def _embed_with_openai(texts: list[str]) -> list[list[float]]:
    """Call OpenAI to embed a list of texts, in safe-sized batches."""
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise EmbeddingError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    vectors: list[list[float]] = []

    # Send the texts in batches so one request never gets too large.
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start:start + EMBED_BATCH_SIZE]
        try:
            response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        except Exception as error:
            raise EmbeddingError(f"OpenAI embedding request failed: {error}")

        # response.data comes back in the SAME order as the input batch.
        for item in response.data:
            vectors.append(item.embedding)

    return vectors


def embed_texts(texts: list[str]) -> list[list[float]]:
    #Turn a list of texts into a list of embedding vectors.
  
    if not texts:
        return []

    if getattr(settings, "USE_FAKE_EMBEDDINGS", True):
        vectors = [_fake_embedding(text) for text in texts]
    else:
        vectors = _embed_with_openai(texts)

    # every vector must be the right length, or the later database
    # insert into VectorField(1536) will fail with a confusing error.
    for vector in vectors:
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise EmbeddingError(
                f"Expected {EMBEDDING_DIMENSIONS}-dim vectors, got {len(vector)}"
            )

    return vectors


def embed_text(text: str) -> list[float]:
    """Embed a single text. Used for the student's question at query time."""
    return embed_texts([text])[0]