import logging

from src.domain.loader import load_domain_config

logger = logging.getLogger(__name__)


def apply_routing_rules(
    classification: dict,
    custom_fields: dict,
    domain_id: str = "sfda",
) -> dict:
    """
    Apply rule-based routing from domain config.
    Rules take priority over LLM suggestion when they match.
    Returns updated classification dict.
    """
    config = load_domain_config(domain_id)
    request_type = custom_fields.get("request_type") or classification["request_type"]
    product_type = custom_fields.get("product_type", "")

    # Try each routing rule in order
    for rule in config.routing_rules:
        try:
            # Evaluate condition with ticket fields as context
            match = eval(
                rule.condition,
                {"__builtins__": {}},
                {"request_type": request_type, "product_type": product_type},
            )
            if match:
                logger.info(
                    f"Rule matched: {rule.condition} → "
                    f"dept={rule.department}, priority={rule.priority}"
                )
                classification["department"] = rule.department
                classification["priority"] = rule.priority
                classification["routed_by"] = "rule"
                return classification
        except Exception as e:
            logger.warning(f"Rule evaluation failed: {rule.condition} — {e}")
            continue

    # No rule matched — trust the LLM
    classification["routed_by"] = "llm"
    logger.info(
        f"No rule matched. Using LLM suggestion: "
        f"dept={classification['department']}, priority={classification['priority']}"
    )
    return classification