"""
FoodWise AI - Application Entry Point
"""
from app import create_app
import os

app = create_app(os.getenv("FLASK_ENV", "production"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
