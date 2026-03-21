"""
FoodWise AI - Flask Application Factory
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_mail import Mail
from flask_migrate import Migrate
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
mail = Mail()
migrate = Migrate()


def create_app(config_name=None):
    """Application factory pattern."""
    app = Flask(__name__)

    # Load configuration
    from app.config import config_map
    cfg = config_name or os.getenv("FLASK_ENV", "development")
    app.config.from_object(config_map[cfg])

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    # CORS configuration
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get("CORS_ORIGINS", "http://localhost:3000").split(","),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
            "supports_credentials": True
        }
    })

    # Setup logging
    if not app.debug:
        os.makedirs("logs", exist_ok=True)
        file_handler = RotatingFileHandler("logs/foodwise.log", maxBytes=10240000, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("FoodWise AI startup")

    # Register blueprints
    with app.app_context():
        from app.auth.routes import auth_bp
        from app.restaurant.routes import restaurant_bp
        from app.ngo.routes import ngo_bp
        from app.admin.routes import admin_bp
        from app.matching.routes import matching_bp
        from app.notifications.routes import notifications_bp
        from app.ml.routes import ml_bp

        app.register_blueprint(auth_bp, url_prefix="/api/auth")
        app.register_blueprint(restaurant_bp, url_prefix="/api/restaurant")
        app.register_blueprint(ngo_bp, url_prefix="/api/ngo")
        app.register_blueprint(admin_bp, url_prefix="/api/admin")
        app.register_blueprint(matching_bp, url_prefix="/api/matching")
        app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
        app.register_blueprint(ml_bp, url_prefix="/api/ml")

        # JWT error handlers
        @jwt.expired_token_loader
        def expired_token_callback(jwt_header, jwt_payload):
            return {"error": "Token has expired", "code": "TOKEN_EXPIRED"}, 401

        @jwt.invalid_token_loader
        def invalid_token_callback(error):
            return {"error": "Invalid token", "code": "INVALID_TOKEN"}, 401

        @jwt.unauthorized_loader
        def missing_token_callback(error):
            return {"error": "Authorization token required", "code": "MISSING_TOKEN"}, 401

        # Health check endpoint
        @app.route("/api/health")
        def health_check():
            return {
                "status": "healthy",
                "service": "FoodWise AI",
                "version": "1.0.0"
            }, 200

        # Error handlers
        @app.errorhandler(400)
        def bad_request(e):
            return {"error": "Bad request", "message": str(e)}, 400

        @app.errorhandler(404)
        def not_found(e):
            return {"error": "Resource not found"}, 404

        @app.errorhandler(405)
        def method_not_allowed(e):
            return {"error": "Method not allowed"}, 405

        @app.errorhandler(500)
        def internal_error(e):
            db.session.rollback()
            app.logger.error(f"Internal error: {e}")
            return {"error": "Internal server error"}, 500

        # Initialize scheduler for background tasks
        _init_scheduler(app)

    return app


def _init_scheduler(app):
    """Initialize background task scheduler."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.matching.service import MatchingService
        from app.notifications.service import NotificationService

        scheduler = BackgroundScheduler()

        # Auto-match every 15 minutes
        scheduler.add_job(
            func=lambda: _run_in_context(app, MatchingService.run_auto_matching),
            trigger="interval",
            minutes=15,
            id="auto_match"
        )

        # Check expiring food every 30 minutes
        scheduler.add_job(
            func=lambda: _run_in_context(app, NotificationService.send_expiry_alerts),
            trigger="interval",
            minutes=30,
            id="expiry_alerts"
        )

        # Mark expired listings every hour
        scheduler.add_job(
            func=lambda: _run_in_context(app, _expire_listings),
            trigger="interval",
            hours=1,
            id="expire_listings"
        )

        scheduler.start()
        app.logger.info("Background scheduler started")
    except Exception as e:
        app.logger.warning(f"Scheduler init failed: {e}")


def _run_in_context(app, func):
    """Run function within app context."""
    with app.app_context():
        try:
            func()
        except Exception as e:
            app.logger.error(f"Scheduled task error: {e}")


def _expire_listings():
    """Mark expired food listings."""
    from datetime import datetime
    from app.models.food_listing import FoodListing
    db.session.query(FoodListing).filter(
        FoodListing.expiry_time <= datetime.utcnow(),
        FoodListing.status == "available"
    ).update({"status": "expired"})
    db.session.commit()
