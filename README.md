<div align="center">

# تذكرة — Tazkera

**AI Ticket Intelligence Layer for Any Helpdesk**

Pluggable AI system that auto-classifies support tickets, routes them to the right department, and generates response suggestions using RAG — built for Arabic-first government and enterprise helpdesks.

[Live Demo](https://app-tazkera-dev.azurewebsites.net) · [API Docs](https://app-tazkera-dev.azurewebsites.net/docs) · [Architecture](#architecture)

</div>

---

## What it does

Tazkera sits on top of any helpdesk system and adds an AI intelligence layer. When a ticket comes in:

1. **Classifies it** — GPT-4o reads the ticket and determines type, department, and priority with confidence scoring
2. **Routes it** — A hybrid engine applies deterministic rules first, falls back to LLM suggestions when no rule matches
3. **Suggests a response** — RAG retrieves relevant knowledge base articles via pgvector similarity search, then GPT-4o generates a grounded, professional Arabic response
4. **Syncs back** — Results are pushed back to the source helpdesk (Odoo, Zendesk, or any webhook-based system)

The system is **domain-agnostic** — switching from SFDA (food & drug authority) to a municipality helpdesk is a single YAML config file. Zero code changes.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Helpdesk Connectors                   │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐  │
│   │  Odoo   │  │ Zendesk │  │Freshdesk│  │ Webhook  │  │
│   └────┬────┘  └────┬────┘  └────┬────┘  └────┬─────┘  │
│        └─────────┬──┴───────────┘              │        │
└──────────────────┼─────────────────────────────┘        │
                   ▼                                       │
         ┌─────────────────┐                              │
         │  Ticket Adapter  │  Normalize to unified schema │
         └────────┬────────┘                              │
                  ▼                                        │
    ┌──────────────────────────────────┐                  │
    │         AI Engine                 │                  │
    │  ┌──────────┐  ┌────────┐       │                  │
    │  │ Classify  │→│ Route  │       │  LangGraph       │
    │  │ (GPT-4o)  │  │(Rules+ │       │  Workflow        │
    │  │           │  │  LLM)  │       │                  │
    │  └──────────┘  └────────┘       │                  │
    │  ┌──────────────────────┐       │                  │
    │  │  RAG Response        │       │                  │
    │  │  (pgvector + GPT-4o) │       │                  │
    │  └──────────────────────┘       │                  │
    │  ┌──────────────────────┐       │                  │
    │  │  Domain Config (YAML)│       │  Swappable       │
    │  └──────────────────────┘       │                  │
    └──────────────────────────────────┘                  │
                  ▼                                        │
         ┌─────────────────┐                              │
         │   Sync Back      │  Update source helpdesk     │
         └─────────────────┘                              │
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **API** | FastAPI (async) | Non-blocking, auto-generated docs, Pydantic validation |
| **LLM** | Azure OpenAI GPT-4o | Structured JSON output, native Arabic fluency |
| **Embeddings** | text-embedding-3-small | 1536-dim vectors for semantic search |
| **Vector DB** | PostgreSQL + pgvector | No extra infra — vectors live alongside relational data |
| **Orchestration** | LangGraph | Stateful workflow with conditional routing (validate → classify → route) |
| **Database** | PostgreSQL 16 | JSONB for flexible domain-specific fields, GIN indexes |
| **Integration** | Odoo XML-RPC | Bidirectional sync — pull tickets, push AI results back |
| **Deployment** | Docker + Azure App Service | Container-based deployment with ACR |
| **Config** | YAML domain presets | Add a new domain without writing code |

---

## Key Design Decisions

**Why hybrid routing (rules + LLM)?**
Deterministic rules handle clear-cut cases (complaint about drugs → inspection department, urgent). The LLM handles ambiguous tickets where rules don't match. This gives you auditability where you need it and flexibility everywhere else.

**Why JSONB for custom fields?**
Each domain has different ticket fields. SFDA has establishment_type and product_type. A municipality might have district and service_type. JSONB keeps the core schema stable while allowing unlimited domain-specific fields with GIN indexing.

**Why separate classification table?**
`ticket_classifications` is separate from `tickets` so you can re-classify without losing history, compare model versions (GPT-4o vs GPT-4o-mini), and maintain a full audit trail — critical for government systems.

**Why pgvector instead of Pinecone/Weaviate?**
One less service to manage. Vectors live in the same database as tickets and articles. HNSW indexes give sub-millisecond similarity search at this scale. For 10K+ articles, a dedicated vector DB would make sense.

---

## Domain Config System

Adding a new domain is a YAML file:

```yaml
domain:
  id: municipality
  name: Municipality Helpdesk
  language: ar

ticket_fields:
  service_type:
    label_ar: نوع الخدمة
    values:
      - id: cleanliness
        label_ar: نظافة
      - id: roads
        label_ar: طرق
      # ...

departments:
  - id: maintenance
    label_ar: صيانة
    handles: [roads, infrastructure]

routing_rules:
  - condition: "service_type == 'roads'"
    department: maintenance
    priority: high

classification_prompt: |
  Your domain-specific prompt here...
```

No code changes. The AI engine reads the config at runtime and adapts its classification, routing, and response generation.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/domains` | List available domains |
| `GET` | `/api/v1/domains/{id}` | Get domain config |
| `POST` | `/api/v1/tickets` | Create a ticket |
| `GET` | `/api/v1/tickets` | List tickets (filter by domain, status) |
| `GET` | `/api/v1/tickets/{id}` | Get ticket details |
| `POST` | `/api/v1/tickets/{id}/classify` | Run AI classification pipeline |
| `POST` | `/api/v1/tickets/{id}/suggest-response` | Generate RAG response |
| `GET` | `/api/v1/odoo/health` | Check Odoo connection |
| `POST` | `/api/v1/odoo/sync-in` | Pull tickets from Odoo |
| `POST` | `/api/v1/odoo/sync-back/{id}` | Push AI results to Odoo |

Full interactive docs at [`/docs`](https://app-tazkera-dev.azurewebsites.net/docs)

---

## Local Setup

```bash
# Clone
git clone https://github.com/Mohamed-Tarig/tazkera.git
cd tazkera

# Environment
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Copy and fill environment variables
cp .env.example .env

# Start database (PostgreSQL + pgvector)
docker compose up -d

# Run migrations
alembic upgrade head

# Seed with synthetic data (200 tickets + 38 KB articles)
python scripts/seed_db.py

# Generate embeddings
python scripts/generate_embeddings.py

# Start the server
uvicorn src.main:app --reload
```

Open http://localhost:8000 for the dashboard, http://localhost:8000/docs for the API.

---

## Project Structure

```
tazkera/
├── configs/                  # Domain presets (YAML)
│   └── sfda.yaml             # SFDA — first domain pack
├── src/
│   ├── adapters/             # Helpdesk connectors
│   │   ├── base.py           # Abstract interface
│   │   ├── webhook.py        # Generic webhook
│   │   └── odoo.py           # Odoo XML-RPC
│   ├── api/v1/               # FastAPI endpoints
│   ├── domain/               # Config loader + validation
│   ├── models/               # SQLAlchemy ORM
│   ├── schemas/              # Pydantic contracts
│   ├── services/             # AI logic
│   │   ├── classifier.py     # GPT-4o classification
│   │   ├── embeddings.py     # Vector generation
│   │   ├── rag.py            # Retrieval + response
│   │   └── router_engine.py  # Rule-based routing
│   ├── workflows/            # LangGraph pipelines
│   │   └── intake.py         # Validate → Classify → Route
│   └── static/               # Dashboard UI
├── scripts/                  # Data generation + seeding
├── Dockerfile
└── docker-compose.yml
```

---

## Live Demo

**Dashboard**: https://app-tazkera-dev.azurewebsites.net

**Try it:**
1. Click any ticket to open the detail panel
2. Click **"صنّف الآن"** — watch GPT-4o classify it in real-time
3. Click **"اقترح رد"** — see RAG retrieve relevant articles and generate a professional Arabic response

---

## Cost

Running in production on Azure:

| Resource | Monthly Cost |
|----------|-------------|
| Azure OpenAI (GPT-4o + embeddings) | ~$5-15 (usage-based) |
| Azure PostgreSQL Flexible (B1ms) | ~$15 |
| Azure App Service (B1) | ~$13 |
| Azure Container Registry (Basic) | ~$5 |
| **Total** | **~$38-48/month** |

---

## License

MIT

---

Built by [Mohamed Tarig](https://github.com/Mohamed-Tarig)
