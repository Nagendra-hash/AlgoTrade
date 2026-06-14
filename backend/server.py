"""
ASGI entrypoint for supervisor — re-exports the FastAPI app from app.main.
This shim lets `uvicorn server:app` work while keeping the modular layout under app/.
"""
from app.main import app

__all__ = ["app"]
