from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str = ""
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
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    REQUIRE_AUTH: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
