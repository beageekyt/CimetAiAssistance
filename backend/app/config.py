from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Vapi
    vapi_api_key: str = ""
    vapi_public_key: str = ""
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""
    vapi_webhook_secret: str = ""

    # Handoff
    human_handoff_number: str = ""
    human_agent_name: str = "Aarav"

    # DNC gate
    enforce_calling_hours: bool = False
    calling_hours_start: int = 9
    calling_hours_end: int = 20

    # Sandbox
    journey_sandbox_url: str = ""

    # Offline LLM (optional)
    llm_provider: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"

    # CORS
    frontend_origin: str = "http://localhost:5173"

    vapi_base_url: str = "https://api.vapi.ai"


@lru_cache
def get_settings() -> Settings:
    return Settings()
