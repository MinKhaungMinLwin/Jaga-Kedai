from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # AI: "auto" uses an AI Studio key when present, otherwise Vertex AI with the
    # Cloud Run service account; "off" runs the deterministic fallbacks only.
    ai_backend: Literal["auto", "vertex", "gemini_api", "off"] = Field(
        default="auto", validation_alias="KEDAI_AI_BACKEND"
    )
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY", repr=False)
    gcp_project: str | None = Field(
        default=None, validation_alias=AliasChoices("GOOGLE_CLOUD_PROJECT", "KEDAI_GCP_PROJECT")
    )
    gcp_location: str = Field(default="global", validation_alias="GOOGLE_CLOUD_LOCATION")
    model: str = Field(default="gemini-3.5-flash-lite", validation_alias="KEDAI_MODEL")
    vision_model: str | None = Field(default=None, validation_alias="KEDAI_VISION_MODEL")
    tts_model: str = Field(default="gemini-2.5-flash-preview-tts", validation_alias="KEDAI_TTS_MODEL")
    tts_voice: str = Field(default="Kore", validation_alias="KEDAI_TTS_VOICE")
    ai_timeout_seconds: int = Field(default=45, validation_alias="KEDAI_AI_TIMEOUT_SECONDS")

    # Data: Firestore in Cloud Run, an in-process store for local dev and tests.
    store: Literal["memory", "firestore"] = Field(default="memory", validation_alias="KEDAI_STORE")
    firestore_database: str = Field(default="(default)", validation_alias="KEDAI_FIRESTORE_DATABASE")
    shop_id: str = Field(default="demo", validation_alias="KEDAI_SHOP_ID")

    admin_token: str | None = Field(default=None, validation_alias="KEDAI_ADMIN_TOKEN", repr=False)
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"], validation_alias="KEDAI_CORS_ORIGINS"
    )
    ai_requests_per_minute: int = Field(default=20, validation_alias="KEDAI_AI_REQUESTS_PER_MINUTE")
    max_upload_bytes: int = Field(default=8 * 1024 * 1024, validation_alias="KEDAI_MAX_UPLOAD_BYTES")

    # Google Cloud Trace for each AI action (needs GOOGLE_CLOUD_PROJECT). Usage/cost logs are always written.
    cloud_trace: bool = Field(default=False, validation_alias="KEDAI_CLOUD_TRACE")
    # Also attach the shopkeeper's question and Kaki's reply to traces (off: they are customer data).
    trace_content: bool = Field(default=False, validation_alias="KEDAI_TRACE_CONTENT")

    @field_validator("gemini_api_key", "gcp_project", "admin_token", "vision_model", mode="before")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        return value or None

    @property
    def resolved_ai_backend(self) -> str:
        if self.ai_backend != "auto":
            return self.ai_backend
        if self.gemini_api_key:
            return "gemini_api"
        if self.gcp_project:
            return "vertex"
        return "off"


@lru_cache
def get_settings() -> Settings:
    return Settings()
