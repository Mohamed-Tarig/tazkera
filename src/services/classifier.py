import json
import logging

from openai import AzureOpenAI

from src.config import settings
from src.domain.loader import load_domain_config

logger = logging.getLogger(__name__)

client = AzureOpenAI(
    api_key=settings.azure_openai_api_key,
    api_version=settings.azure_openai_api_version,
    azure_endpoint=settings.azure_openai_endpoint,
)


def classify_ticket(
    subject: str,
    description: str,
    custom_fields: dict,
    domain_id: str = "sfda",
) -> dict:
    """
    Send a ticket to GPT-4o for classification.
    Returns dict with: request_type, department, priority, confidence, reasoning.
    """
    config = load_domain_config(domain_id)

    # Build available values from domain config
    request_types = ", ".join(
        f.id for f in config.ticket_fields["request_type"].values
    )
    departments = ", ".join(d.id for d in config.departments)

    # Fill the prompt template from the domain config
    prompt = config.classification_prompt.format(
        subject=subject,
        description=description,
        establishment_type=custom_fields.get("establishment_type", "غير محدد"),
        product_type=custom_fields.get("product_type", "غير محدد"),
        request_types=request_types,
        departments=departments,
    )

    logger.info(f"Classifying ticket: {subject[:50]}...")

    response = client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=[
            {
                "role": "system",
                "content": (
                    "أنت مصنّف تذاكر خبير. أجب بـ JSON فقط بدون أي نص إضافي."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,  # Low temp = consistent classification
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    logger.info(f"Raw LLM response: {raw}")

    result = json.loads(raw)

    # Validate and normalize the result
    return {
        "request_type": result.get("request_type", "inquiry"),
        "department": result.get("department", "registration"),
        "priority": result.get("priority", "medium"),
        "confidence": float(result.get("confidence", 0.5)),
        "reasoning": result.get("reasoning", ""),
        "model_version": settings.azure_openai_deployment,
    }