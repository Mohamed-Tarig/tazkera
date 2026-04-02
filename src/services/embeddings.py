import hashlib
import logging

from openai import AzureOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

client = AzureOpenAI(
    api_key=settings.azure_openai_embedding_key or settings.azure_openai_api_key,
    api_version=settings.azure_openai_api_version,
    azure_endpoint=settings.azure_openai_embedding_endpoint or settings.azure_openai_endpoint,
)


def get_embedding(text: str) -> list[float]:
    """Generate embedding for a single text using Azure OpenAI."""
    # Clean and truncate (embedding model has 8191 token limit)
    text = text.strip().replace("\n", " ")
    if len(text) > 8000:
        text = text[:8000]

    response = client.embeddings.create(
        model=settings.azure_openai_embedding_deployment,
        input=text,
    )
    return response.data[0].embedding


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts in one API call."""
    cleaned = []
    for t in texts:
        t = t.strip().replace("\n", " ")
        if len(t) > 8000:
            t = t[:8000]
        cleaned.append(t)

    response = client.embeddings.create(
        model=settings.azure_openai_embedding_deployment,
        input=cleaned,
    )
    return [item.embedding for item in response.data]


def content_hash(text: str) -> str:
    """SHA-256 hash to detect if content changed."""
    return hashlib.sha256(text.encode()).hexdigest()