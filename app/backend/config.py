from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SUPABASE_URL: str = "https://gachxhquivfvwejytsbb.supabase.co"
    SUPABASE_KEY: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdhY2h4aHF1aXZmdndlanl0c2JiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU3MTczMTksImV4cCI6MjA5MTI5MzMxOX0.AjHenUD4i_xErSORT8WzIpDt3Vvrn5pU2tMTevxzZ3Y"
    ANTHROPIC_API_KEY: str = ""
    BREVO_API_KEY: str = ""
    FRONTEND_URL: str = "http://localhost:3000"
    GOOGLE_API_KEY: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
