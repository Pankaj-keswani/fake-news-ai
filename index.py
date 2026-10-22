"""Vercel entrypoint: exposes the Flask app from backend/app.py as `app`."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from app import app  # noqa: E402,F401
