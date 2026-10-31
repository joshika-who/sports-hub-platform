import os
import sys

# Add the `backend` directory to Python's module search path so Vercel's
# serverless runtime can import `app.main` and `services.*` cleanly.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.main import app  # noqa: E402

__all__ = ["app"]
