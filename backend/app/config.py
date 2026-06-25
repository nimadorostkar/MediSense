"""Central configuration — all environment config + feature flags (spec §2, §9).

Every tunable lives here so the rest of the codebase never reads os.environ
directly. Secrets are sourced from the environment only (spec §1.8 / §18.1).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "MediSense"
    environment: str = Field(default="dev")
    log_level: str = Field(default="INFO")
    data_region: str = Field(default="cn-pilot")

    # ── Datastore ────────────────────────────────────────────────────────────
    database_url: str = Field(default="sqlite+aiosqlite:///./medisense.db")
    redis_url: str | None = Field(default=None)

    # ── Zhipu GLM / embeddings ───────────────────────────────────────────────
    zhipu_api_key: str | None = Field(default=None)
    zhipu_base_url: str = Field(default="https://open.bigmodel.cn/api/paas/v4")
    llm_chat_model: str = Field(default="glm-4.6")
    embedding_model: str = Field(default="embedding-3")
    llm_reasoning: bool = Field(default=False)
    llm_max_tokens: int = Field(default=1024)
    llm_timeout_seconds: float = Field(default=12.0)

    # ── Auth ─────────────────────────────────────────────────────────────────
    dev_auth: bool = Field(default=True)
    dev_auth_secret: str = Field(default="dev-only-change-me")
    oidc_issuer: str | None = Field(default=None)
    oidc_audience: str = Field(default="medisense")
    oidc_jwks_url: str | None = Field(default=None)

    # ── HTTP / CORS ──────────────────────────────────────────────────────────
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:8787")
    rate_limit_per_minute: int = Field(default=120)

    # ── Version stamps (spec §3.5, §14.2) ────────────────────────────────────
    model_version: str = Field(default="dx-2026.06.1-pilot")
    ruleset_version: str = Field(default="rules-2026.06.1")
    drugref_version: str = Field(default="drugref-2026.06.1")
    prompt_version: str = Field(default="prompt-2026.06.1")
    embedding_version: str = Field(default="emb-2026.06.1")

    # ── Integration ──────────────────────────────────────────────────────────
    fhir_base_url: str | None = Field(default=None)
    fhir_write_back: bool = Field(default=False)

    # ── Engine tuning ────────────────────────────────────────────────────────
    retrieval_k: int = Field(default=8)
    ood_similarity_floor: float = Field(default=0.28)

    @field_validator("environment")
    @classmethod
    def _normalize_env(cls, v: str) -> str:
        return v.strip().lower()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def datastore_label(self) -> str:
        return "sqlite" if self.is_sqlite else "postgres"

    @property
    def llm_configured(self) -> bool:
        """The GLM reasoning layer is only live when flagged on AND a key exists."""
        return bool(self.llm_reasoning and self.zhipu_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
