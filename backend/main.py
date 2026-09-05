"""
main.py
=======
FastAPI application re-export for top-level imports.
The primary implementation resides in `app/main.py`.
"""

from app.main import app, lifespan

__all__ = ["app", "lifespan"]
