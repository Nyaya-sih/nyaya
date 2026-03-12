"""
Configuration management using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""

from typing import List
import json
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Database Configuration
    database_url: str = Field(
        default="postgresql://nyaya_user:nyaya_password@localhost:5432/nyaya_ai",
        description="PostgreSQL connection string",
    )
    postgres_user: str = "nyaya_user"
    postgres_password: str = "nyaya_password"
    postgres_db: str = "nyaya_ai"

    # Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection string"
    )

    # Qdrant Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Similar Case Retrieval
    default_top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Default number of results for similarity search",
    )
    vector_search_candidates: int = Field(
        default=20,
        ge=5,
        le=200,
        description="Number of vector candidates before reranking",
    )
    reranker_candidate_limit: int = Field(
        default=12,
        ge=5,
        le=100,
        description="Maximum candidates passed to reranker",
    )
    similarity_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score to include in results",
    )
    enable_reranking: bool = Field(
        default=True, description="Enable cross-encoder reranking"
    )
    enable_llm_explanation: bool = Field(
        default=True, description="Enable on-demand LLM explanations"
    )
    enable_query_llm_metadata: bool = Field(
        default=False,
        description="Enable lightweight LLM metadata extraction for queries",
    )
    query_metadata_model: str = Field(
        default="gpt-4o-mini", description="Model to use for query metadata extraction"
    )
    enable_fulltext_search: bool = Field(
        default=True, description="Prefer full-text-lite collection when available"
    )
    reranker_vector_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for vector similarity in final rerank blend",
    )
    reranker_model_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight for cross-encoder score in final rerank blend",
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API port")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"], description="Allowed CORS origins"
    )

    # AWS S3 Configuration (Public Bucket)
    s3_bucket_name: str = "indian-high-court-judgments"
    s3_region: str = "ap-south-1"

    # LLM API Keys
    openai_api_key: str = Field(
        default="", description="OpenAI API key for LLM extraction"
    )
    anthropic_api_key: str = Field(
        default="", description="Anthropic API key for Claude models"
    )
    google_api_key: str = Field(
        default="", description="Google API key for Gemini models"
    )

    # LLM Model Configuration
    extraction_model: str = Field(
        default="gpt-4o-mini", description="Model to use for metadata extraction"
    )
    extraction_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM extraction (lower = more deterministic)",
    )
    max_retries: int = Field(
        default=3, ge=1, description="Maximum number of retries for failed API calls"
    )
    retry_delay: int = Field(
        default=2, ge=1, description="Delay in seconds between retries"
    )

    # Processing Configuration
    batch_size: int = Field(
        default=10, ge=1, description="Batch size for processing documents"
    )
    max_concurrent_requests: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of concurrent LLM API requests",
    )
    download_max_cases: int = Field(
        default=100, ge=1, description="Maximum number of cases to download per session"
    )

    # Court Codes to Download
    target_courts: List[str] = Field(
        default=["DL_HC", "BH_HC"], description="List of court codes to download"
    )
    target_years: List[int] = Field(
        default=[2024, 2023], description="List of years to download"
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    log_file: str = Field(
        default="data/logs/pipeline.log", description="Path to log file"
    )

    @field_validator("target_courts", mode="before")
    @classmethod
    def parse_courts(cls, v):
        """Parse comma-separated court codes from env var."""
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        return v

    @field_validator("target_years", mode="before")
    @classmethod
    def parse_years(cls, v):
        """Parse comma-separated years from env var."""
        if isinstance(v, str):
            return [int(y.strip()) for y in v.split(",") if y.strip()]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated CORS origins."""
        if isinstance(v, str):
            text = v.strip()
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        return [
                            str(origin).strip()
                            for origin in parsed
                            if str(origin).strip()
                        ]
                except json.JSONDecodeError:
                    return [
                        origin.strip() for origin in text.split(",") if origin.strip()
                    ]
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return v

    @field_validator(
        "enable_reranking",
        "enable_llm_explanation",
        "enable_query_llm_metadata",
        "enable_fulltext_search",
        mode="before",
    )
    @classmethod
    def parse_bool(cls, v):
        """Parse boolean values from env vars."""
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(v)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is one of the allowed values."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v.upper()

    def has_llm_key(self) -> bool:
        """Check if at least one LLM API key is configured."""
        return bool(
            self.openai_api_key or self.anthropic_api_key or self.google_api_key
        )

    def get_available_models(self) -> List[str]:
        """Get list of available LLM providers based on configured API keys."""
        available = []
        if self.openai_api_key:
            available.append("openai")
        if self.anthropic_api_key:
            available.append("anthropic")
        if self.google_api_key:
            available.append("google")
        return available


# Global settings instance
settings = Settings()
