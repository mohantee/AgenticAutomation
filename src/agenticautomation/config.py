"""Environment-aware configuration for AgenticAutomation.

Supports dev (local machine), test, and prod (AWS cloud) environments.
All settings are derived from environment variables with sensible defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Strongly-typed configuration loaded from environment variables."""

    # --- Core Environment ---
    env: str = field(default_factory=lambda: os.getenv("ENV", "dev"))

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    # --- Storage Backend ---
    @property
    def storage_backend(self) -> str:
        explicit = os.getenv("STORAGE_BACKEND")
        if explicit:
            return explicit
        return "local" if self.is_dev else "s3"

    # --- Local Storage Paths (dev mode) ---
    @property
    def local_storage_path(self) -> str:
        return os.getenv("LOCAL_STORAGE_PATH", "./data/workflows")

    @property
    def local_input_path(self) -> str:
        return os.getenv("LOCAL_INPUT_PATH", "./sample_files")

    # --- S3 Configuration (test/prod mode) ---
    @property
    def s3_input_bucket(self) -> str:
        return os.getenv("S3_INPUT_BUCKET", f"agenticautomation-input-{self.env}")

    @property
    def s3_data_bucket(self) -> str:
        return os.getenv("S3_DATA_BUCKET", f"agenticautomation-data-{self.env}")

    @property
    def aws_region(self) -> str:
        return os.getenv("AWS_REGION", "ap-south-1")

    # --- Bedrock ---
    @property
    def mock_bedrock(self) -> bool:
        mock_val = os.getenv("MOCK_BEDROCK")
        if mock_val is not None:
            return mock_val.lower() in ("true", "1", "yes")
        return self.is_dev

    # --- API ---
    @property
    def api_port(self) -> int:
        return int(os.getenv("API_PORT", "5000"))

    def ensure_local_dirs(self) -> None:
        """Create local storage directories if running in dev mode."""
        if self.is_dev:
            Path(self.local_storage_path).mkdir(parents=True, exist_ok=True)
            Path(self.local_input_path).mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return (
            f"Config(env={self.env!r}, storage_backend={self.storage_backend!r}, "
            f"mock_bedrock={self.mock_bedrock}, is_dev={self.is_dev})"
        )


# Singleton instance — import this from other modules.
config = Config()
