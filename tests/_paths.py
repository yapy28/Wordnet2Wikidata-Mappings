"""Make scripts/ importable and locate the current run directory."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
RUN_DIR = ROOT / "data" / "output" / "20260929"
