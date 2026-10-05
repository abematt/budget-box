import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
os.environ.setdefault("SOURCE", "demo")
os.environ.setdefault("DEMO_DIR", str(ROOT / "tests" / "fixtures"))
os.environ.setdefault("DEVICE_TOKEN", "test-token")
os.environ.setdefault("DATA_DIR", str(ROOT / ".pytest_cache" / "data"))
