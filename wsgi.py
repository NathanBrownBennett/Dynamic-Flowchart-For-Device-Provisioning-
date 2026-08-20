"""Production WSGI entrypoint for a reverse-proxy hosted deployment."""

from app import app

__all__ = ['app']
