"""Keep bundled resources separate from portable, persistent user data."""
from pathlib import Path
import sys

RESOURCE_ROOT = Path(__file__).resolve().parent
USER_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else RESOURCE_ROOT
