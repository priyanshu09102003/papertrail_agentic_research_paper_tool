"""PaperTrail backend application package."""

from pathlib import Path
import sys

# Automatically ensure backend/.venv site-packages is in sys.path even if uvicorn is invoked globally
_backend_root = Path(__file__).resolve().parent.parent
_venv_site_packages = _backend_root / ".venv" / "Lib" / "site-packages"
if _venv_site_packages.exists() and str(_venv_site_packages) not in sys.path:
    sys.path.insert(0, str(_venv_site_packages))

__version__ = "0.1.0"
