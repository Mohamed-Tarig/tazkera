import logging
import xmlrpc.client

from src.config import settings
from src.adapters.base import BaseAdapter
from src.schemas.ticket import TicketCreate

logger = logging.getLogger(__name__)


class OdooAdapter(BaseAdapter):
    """
    Odoo adapter — connects via XML-RPC to project.task model.
    Maps Odoo tasks to Tazkera unified ticket format.
    """

    def __init__(self):
        self.url = settings.odoo_url
        self.db = settings.odoo_db
        self.username = settings.odoo_username
        self.password = settings.odoo_password
        self.project_name = settings.odoo_project_name
        self.uid = None
        self.models = None

    def _connect(self):
        """Authenticate and cache the connection."""
        if self.uid and self.models:
            return

        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        self.uid = common.authenticate(self.db, self.username, self.password, {})

        if not self.uid:
            raise ConnectionError("Odoo authentication failed")

        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        logger.info(f"Connected to Odoo as uid={self.uid}")

    def _execute(self, model: str, method: str, *args, **kwargs):
        """Execute an Odoo RPC call."""
        self._connect()
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, method, *args, **kwargs
        )

    def _get_project_id(self) -> int:
        """Find the project ID by name."""
        projects = self._execute(
            "project.project", "search_read",
            [[["name", "=", self.project_name]]],
            {"fields": ["id", "name"], "limit": 1},
        )
        if not projects:
            raise ValueError(f"Project '{self.project_name}' not found in Odoo")
        return projects[0]["id"]

    async def fetch_new_tickets(self) -> list[TicketCreate]:
        """Pull unprocessed tasks from Odoo project."""
        project_id = self._get_project_id()

        # Fetch tasks that haven't been synced (no tazkera tag)
        tasks = self._execute(
            "project.task", "search_read",
            [[
                ["project_id", "=", project_id],
            ]],
            {"fields": [
                "id", "name", "description", "create_date",
                "partner_id", "stage_id", "tag_ids",
            ]},
        )

        # Filter out already-synced tasks in Python
        synced_tag_ids = self._execute(
            "project.tags", "search",
            [[["name", "=", "tazkera-synced"]]],
        )
        synced_tag_id = synced_tag_ids[0] if synced_tag_ids else None

        tasks = [
            t for t in tasks
            if not synced_tag_id or synced_tag_id not in t.get("tag_ids", [])
        ]

        logger.info(f"Fetched {len(tasks)} new tasks from Odoo")

        tickets = []
        for task in tasks:
            # Clean description (Odoo stores HTML)
            desc = task.get("description") or ""
            desc = desc.replace("<br>", "\n").replace("<p>", "").replace("</p>", "\n")
            # Strip remaining HTML tags
            import re
            desc = re.sub(r"<[^>]+>", "", desc).strip()

            if not desc:
                desc = task["name"]  # Use title as fallback

            partner_name = task["partner_id"][1] if task.get("partner_id") else None

            ticket = TicketCreate(
                domain_id="sfda",
                source_system="odoo",
                source_ticket_id=str(task["id"]),
                subject=task["name"],
                description=desc,
                submitter_name=partner_name,
                submitter_email=None,
                custom_fields={
                    "odoo_stage": task["stage_id"][1] if task.get("stage_id") else None,
                },
            )
            tickets.append(ticket)

        return tickets

    async def sync_back(self, ticket_id: str, updates: dict) -> bool:
        """Push classification and response back to Odoo task."""
        try:
            odoo_task_id = int(ticket_id)

            # Build the note to post on the task
            classification = updates.get("classification", {})
            suggestion = updates.get("suggestion", {})

            note_parts = ["<h3>🤖 Tazkera AI Analysis</h3>"]

            if classification:
                note_parts.append(
                    f"<p><strong>التصنيف:</strong> {classification.get('request_type', '-')}<br/>"
                    f"<strong>القسم:</strong> {classification.get('department', '-')}<br/>"
                    f"<strong>الأولوية:</strong> {classification.get('priority', '-')}<br/>"
                    f"<strong>الثقة:</strong> {classification.get('confidence', '-')}</p>"
                )

            if suggestion.get("response_text"):
                response_html = suggestion["response_text"].replace("\n", "<br/>")
                note_parts.append(
                    f"<h4>الرد المقترح:</h4><p>{response_html}</p>"
                )

                if suggestion.get("needs_human_review"):
                    note_parts.append(
                        f"<p>⚠️ <em>{suggestion.get('review_reason', 'يحتاج مراجعة بشرية')}</em></p>"
                    )

            note = "".join(note_parts)

            # Post as internal note on the task
            self._execute(
                "project.task", "message_post",
                [[odoo_task_id]],
                {
                    "body": note,
                    "message_type": "comment",
                    "subtype_xmlid": "mail.mt_note",
                },
            )

            # Add "tazkera-synced" tag
            self._ensure_tag("tazkera-synced")
            tag_ids = self._execute(
                "project.tags", "search",
                [[["name", "=", "tazkera-synced"]]],
            )
            if tag_ids:
                self._execute(
                    "project.task", "write",
                    [[odoo_task_id], {"tag_ids": [(4, tag_ids[0])]}],
                )

            # Set priority if available
            priority_map = {"urgent": "1", "high": "1", "medium": "0", "low": "0"}
            if classification.get("priority"):
                odoo_priority = priority_map.get(classification["priority"], "0")
                self._execute(
                    "project.task", "write",
                    [[odoo_task_id], {"priority": odoo_priority}],
                )

            logger.info(f"Synced back to Odoo task {odoo_task_id}")
            return True

        except Exception as e:
            logger.error(f"Sync back failed for task {ticket_id}: {e}")
            return False

    def _ensure_tag(self, tag_name: str):
        """Create tag if it doesn't exist."""
        existing = self._execute(
            "project.tags", "search",
            [[["name", "=", tag_name]]],
        )
        if not existing:
            self._execute("project.tags", "create", [{"name": tag_name}])

    async def verify_connection(self) -> bool:
        """Health check — can we reach Odoo?"""
        try:
            self._connect()
            self._get_project_id()
            return True
        except Exception as e:
            logger.error(f"Odoo connection failed: {e}")
            return False