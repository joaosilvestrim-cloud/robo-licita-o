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
    # Regex de origens liberadas (além da lista). Cobre qualquer subdomínio de
    # drivedata.com.br e qualquer deploy .vercel.app — evita reconfigurar CORS.
    cors_origin_regex: str = r"https://([a-z0-9-]+\.)*(drivedata\.com\.br|vercel\.app)$"

    # Schema do Postgres onde ficam as tabelas do robô. Isola de outros apps no
    # mesmo banco (ex.: o demo do CRM). "public" = comportamento padrão.
    db_schema: str = "public"

    # Notificação proativa via Telegram (bot grátis: @BotFather).
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # IA — Assistente Sonar via Groq (API compatível com OpenAI).
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"   # llama-3.3 foi aposentado pelo Groq (ago/2026)
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # Porta interna (Render injeta PORT) — usada pelo agente p/ chamar a própria API.
    port: int = 8003

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
