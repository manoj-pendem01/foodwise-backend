"""
FoodWise AI - Application Entry Point
"""
from app import create_app, db
import os

app = create_app(os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "True") == "True"
    )
