"""ASGI runtime entry point. Import application.create_app for isolated tools and tests."""
from .application import create_app

app=create_app()
