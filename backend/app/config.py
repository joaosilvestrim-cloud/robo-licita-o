from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://procurement:procurement-secret@localhost:5432/acraprocurement"
    secret_key: str = "procurement-jwt-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    sso_key: str = "acra-sso-2024"
    office_api_url: str = "http://acra-backend:8000"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@acrasystem.com"
    frontend_url: str = "http://localhost:3003"

    hermes_url: str = "http://hermes:4000"
    hermes_procurement_url: str = "http://hermes-procurement:8004"
    litellm_master_key: str = "Dfc@1947"

    # Intervalo de sincronização em horas
    pncp_sync_interval_hours: int = 6

    # Agendador interno. Em cloud (Render + cron externo) fica desligado.
    enable_scheduler: bool = False

    # Segredo para o cron externo chamar os endpoints de sync sem JWT de usuário.
    cron_secret: str = ""

    # Origens permitidas no CORS. "*" libera geral. Em prod, use a URL do front.
    cors_origins: str = "*"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
