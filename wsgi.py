import os

os.environ.setdefault("UNITYWORKS_CONFIG", "production")

from app import create_app

app = create_app(os.environ.get("UNITYWORKS_CONFIG", "production"))
