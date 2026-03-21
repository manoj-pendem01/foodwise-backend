"""
FoodWise AI - Authentication Routes
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from app.auth.service import AuthService
from app.utils import get_current_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new restaurant or NGO."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    result, status = AuthService.register(data)
    return jsonify(result), status


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate and get JWT tokens."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    result, status = AuthService.login(
        data.get("email"),
        data.get("password")
    )
    return jsonify(result), status


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token."""
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({"access_token": access_token}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    """Get current user profile."""
    user_id = get_jwt_identity()
    result, status = AuthService.get_profile(user_id)
    return jsonify(result), status


@auth_bp.route("/change-password", methods=["PUT"])
@jwt_required()
def change_password():
    """Change user password."""
    user_id = get_jwt_identity()
    data = request.get_json()
    result, status = AuthService.change_password(
        user_id,
        data.get("current_password"),
        data.get("new_password")
    )
    return jsonify(result), status


@auth_bp.route("/update-profile", methods=["PUT"])
@jwt_required()
def update_profile():
    """Update user profile information."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    from app import db

    try:
        if user.role == "restaurant" and user.restaurant:
            r = user.restaurant
            for field in ["name", "description", "phone", "address", "city", "state", "zip_code", "cuisine_type", "seating_capacity", "avg_daily_covers"]:
                if field in data:
                    setattr(r, field, data[field])
            if "latitude" in data:
                r.latitude = float(data["latitude"])
            if "longitude" in data:
                r.longitude = float(data["longitude"])

        elif user.role == "ngo" and user.ngo:
            n = user.ngo
            for field in ["name", "description", "phone", "address", "city", "state", "zip_code", "registration_number", "focus_area", "beneficiaries_count"]:
                if field in data:
                    setattr(n, field, data[field])
            if "latitude" in data:
                n.latitude = float(data["latitude"])
            if "longitude" in data:
                n.longitude = float(data["longitude"])

        db.session.commit()
        result, status = AuthService.get_profile(user.id)
        return jsonify(result), status

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
