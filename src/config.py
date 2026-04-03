from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://tazkera:tazkera_dev@localhost:5433/tazkera"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_api_version: str = "2024-08-01-preview"

    # Azure OpenAI - Embeddings (separate resource)
    azure_openai_embedding_endpoint: str = ""
    azure_openai_embedding_key: str = ""

    # Odoo
    odoo_url: str = ""
    odoo_db: str = ""
    odoo_username: str = ""
    odoo_password: str = ""
    odoo_project_name: str = "SFDA Tickets"

    # App
    domain_config: str = "sfda"
    log_level: str = "INFO"

    model_config = {"env_file": ".env"}


settings = Settings()