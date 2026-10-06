"""Development server:  python run.py
Production:          gunicorn -w 2 -b 0.0.0.0:${PORT:-5000} run:app"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")),
            debug=app.config["APP_ENV"] == "development")
