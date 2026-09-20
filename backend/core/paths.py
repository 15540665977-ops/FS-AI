"""Stable filesystem locations for local and container deployments."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SPECTRAL_DATA_DIR", BACKEND_DIR))
UPLOADS_DIR = DATA_DIR / "uploads"
CHROMA_DIR = Path(os.environ.get("CHROMA_PERSIST_DIR", DATA_DIR / "chroma_db"))
DATABASE_PATH = Path(os.environ.get("SPECTRAL_DATABASE_PATH", DATA_DIR / "spectral_analysis.db"))
