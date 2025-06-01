import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import Dict, Any # For type hinting

load_dotenv() # Load .env file variables

class Settings(BaseSettings):
    # Application settings
    APP_NAME: str = "SaaS Content Generator API"
    API_V1_STR: str = "/api/v1" # Example, not used yet but good to have

    # JWT Settings
    # IMPORTANT: In a production environment, generate a strong, random secret key.
    # You can generate one using: openssl rand -hex 32
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a_very_default_but_not_secure_secret_key_for_dev")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 # Token validity period
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 48 # e.g., 48 hours
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 1 # e.g., 1 hour

    # Gemini API Key (already handled in gemini_service, but good to centralize if needed elsewhere)
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

    # Database URL
    # Example for SQLite: "sqlite:///./saas_content_generator.db"
    # Example for PostgreSQL: "postgresql://user:password@host:port/dbname"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./saas_content_generator.db")

    # Supabase Settings
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://<YOUR_PROJECT_REF_HERE>.supabase.co")
    SUPABASE_JWKS_URI: str = os.getenv("SUPABASE_JWKS_URI", f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json") # Default construction
    # SUPABASE_SERVICE_ROLE_KEY: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY") # If needed for backend calls to Supabase

    # Subscription Tiers Configuration
    # Keys are tier names (e.g., "free", "basic", "premium")
    # Values are dictionaries defining limits and display info for that tier.
    SUBSCRIPTION_TIERS_CONFIG: Dict[str, Dict[str, Any]] = {
        "free": {
            "api_calls": 100,
            "display_name": "Free Tier",
            "description": "Get started with basic access and 100 API calls per month."
        },
        "basic": {
            "api_calls": 1000,
            "display_name": "Basic Tier",
            "description": "Ideal for growing needs, includes 1,000 API calls per month."
        },
        "premium": {
            "api_calls": 10000,
            "display_name": "Premium Tier",
            "description": "Extensive access for power users, with 10,000 API calls per month."
        },
        # "unlimited": {"api_calls": -1} # -1 could signify unlimited, handle in logic
    }
    DEFAULT_SUBSCRIPTION_TIER: str = "free"
    VALID_SUBSCRIPTION_TIERS: list[str] = list(SUBSCRIPTION_TIERS_CONFIG.keys())

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        # If SUPABASE_JWKS_URI depends on SUPABASE_URL, ensure SUPABASE_URL is processed first.
        # Pydantic v2 handles this better, for v1 this might need manual construction if SUPABASE_URL is also from env.

settings = Settings()