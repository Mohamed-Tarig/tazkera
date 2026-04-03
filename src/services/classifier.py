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

    # Build prompt variables dynamically from custom_fields + standard fields
    prompt_vars = {
        "subject": subject,
        "description": description,
        "request_types": request_types,
        "departments": departments,
    }
    # Add all custom fields as available prompt variables
    for key, value in custom_fields.items():
        prompt_vars[key] = value

    # Fill the prompt template, ignoring missing placeholders
    try:
        prompt = config.classification_prompt.format(**prompt_vars)
    except KeyError as e:
        # If a placeholder in the prompt has no matching field, set it to "غير محدد"
        import re
        placeholders = re.findall(r'\{(\w+)\}', config.classification_prompt)
        for ph in placeholders:
            if ph not in prompt_vars:
                prompt_vars[ph] = "غير محدد"
        prompt = config.classification_prompt.format(**prompt_vars)

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