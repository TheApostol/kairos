from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str = ""
    # service_role secret key. Required: with RLS enabled, the backend uses
    # this key to bypass RLS and enforces per-organization scoping itself.
    SUPABASE_SERVICE_KEY: str = ""
    # anon/publishable key. Used to verify user access tokens against the
    # Supabase Auth API (GoTrue).
    SUPABASE_ANON_KEY: str = ""
    # Deprecated: kept as a fallback for SUPABASE_SERVICE_KEY if it is not set.
    SUPABASE_KEY: str = ""

    # Third-party services
    ANTHROPIC_API_KEY: str = ""
    BREVO_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""

    # App URLs
    SENDER_EMAIL: str = "noreply@kairos.com"
    SENDER_NAME: str = "Kairos CRM"
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # Security
    # Comma-separated origins. Example: https://kairos.vercel.app,https://kairosdis.com.ar
    # Includes the production frontend by default so CORS still works even if
    # the ALLOWED_ORIGINS env var isn't configured on the host (e.g. Render).
    ALLOWED_ORIGINS: str = "http://localhost:3000,https://kairos.polkorp.com"
    REQUIRE_AUTH: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
