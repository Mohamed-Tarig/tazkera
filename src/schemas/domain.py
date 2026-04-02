from pydantic import BaseModel


class FieldValue(BaseModel):
    id: str
    label_ar: str


class TicketField(BaseModel):
    label_ar: str
    values: list[FieldValue]


class Department(BaseModel):
    id: str
    label_ar: str
    handles: list[str]


class RoutingRule(BaseModel):
    condition: str
    department: str
    priority: str


class Priority(BaseModel):
    id: str
    label_ar: str
    sla_hours: int


class DomainInfo(BaseModel):
    id: str
    name: str
    name_ar: str
    language: str
    timezone: str


class DomainConfig(BaseModel):
    domain: DomainInfo
    ticket_fields: dict[str, TicketField]
    departments: list[Department]
    routing_rules: list[RoutingRule]
    classification_prompt: str
    priorities: list[Priority]