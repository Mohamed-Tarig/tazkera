import logging
import uuid
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.services.classifier import classify_ticket
from src.services.router_engine import apply_routing_rules

logger = logging.getLogger(__name__)


# -- State schema --
class IntakeState(TypedDict):
    ticket_id: str
    domain_id: str
    subject: str
    description: str
    custom_fields: dict
    classification: dict
    status: str
    error: str


# -- Nodes --

def validate_node(state: IntakeState) -> dict:
    """Validate ticket has minimum required fields."""
    errors = []
    if not state.get("subject") or len(state["subject"].strip()) < 5:
        errors.append("Subject too short (min 5 chars)")
    if not state.get("description") or len(state["description"].strip()) < 10:
        errors.append("Description too short (min 10 chars)")
    if not state.get("domain_id"):
        errors.append("domain_id is required")

    if errors:
        return {"status": "validation_failed", "error": "; ".join(errors)}

    logger.info(f"Validation passed for ticket: {state.get('ticket_id')}")
    return {"status": "validated", "error": ""}


def classify_node(state: IntakeState) -> dict:
    """Call GPT-4o to classify the ticket."""
    try:
        result = classify_ticket(
            subject=state["subject"],
            description=state["description"],
            custom_fields=state.get("custom_fields", {}),
            domain_id=state["domain_id"],
        )
        logger.info(f"Classification: {result}")
        return {"classification": result, "status": "classified"}
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        return {
            "classification": {},
            "status": "classification_failed",
            "error": str(e),
        }


def route_node(state: IntakeState) -> dict:
    """Apply routing rules on top of LLM classification."""
    try:
        routed = apply_routing_rules(
            classification=state["classification"].copy(),
            custom_fields=state.get("custom_fields", {}),
            domain_id=state["domain_id"],
        )
        logger.info(f"Routing result: dept={routed['department']}, by={routed['routed_by']}")
        return {"classification": routed, "status": "routed"}
    except Exception as e:
        logger.error(f"Routing failed: {e}")
        return {"status": "routing_failed", "error": str(e)}


# -- Conditional edges --

def should_continue_after_validation(state: IntakeState) -> str:
    if state.get("status") == "validation_failed":
        return "end"
    return "classify"


def should_continue_after_classification(state: IntakeState) -> str:
    if state.get("status") == "classification_failed":
        return "end"
    return "route"


# -- Build the graph --

def build_intake_graph() -> StateGraph:
    graph = StateGraph(IntakeState)

    # Add nodes
    graph.add_node("validate", validate_node)
    graph.add_node("classify", classify_node)
    graph.add_node("route", route_node)

    # Entry point
    graph.set_entry_point("validate")

    # Conditional edges
    graph.add_conditional_edges(
        "validate",
        should_continue_after_validation,
        {"classify": "classify", "end": END},
    )
    graph.add_conditional_edges(
        "classify",
        should_continue_after_classification,
        {"route": "route", "end": END},
    )

    # Route → END
    graph.add_edge("route", END)

    return graph.compile()


# Singleton — reuse across requests
intake_graph = build_intake_graph()