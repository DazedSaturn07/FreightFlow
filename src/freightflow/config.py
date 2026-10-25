"""Paths and constants; no hidden user-specific locations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path

    @property
    def raw_dir(self) -> Path:
        return self.root / "data" / "raw" / "FAF5.7.1"

    @property
    def source_csv(self) -> Path:
        return self.raw_dir / "FAF5.7.1.csv"

    @property
    def metadata_xlsx(self) -> Path:
        return self.raw_dir / "FAF5_metadata.xlsx"

    @property
    def processed_dir(self) -> Path:
        return self.root / "data" / "processed"

    @property
    def quality_dir(self) -> Path:
        return self.root / "artifacts" / "quality"

    @property
    def export_dir(self) -> Path:
        return self.root / "artifacts" / "exports"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def settings() -> Settings:
    return Settings(project_root())
