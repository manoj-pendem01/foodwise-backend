"""
FoodWise AI - Utility Functions
"""
import re
import math
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# Password Utilities
# ============================================================

def hash_password(password: str) -> str:
    """Hash a password using werkzeug."""
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return check_password_hash(password_hash, password)


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    return True, ""


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


# ============================================================
# Role-Based Access Control Decorators
# ============================================================

def role_required(*roles):
    """Decorator to enforce role-based access."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            from app.models import User
            identity = get_jwt_identity()
            user = User.query.get(identity)
            if not user:
                return jsonify({"error": "User not found"}), 404
            if not user.is_active:
                return jsonify({"error": "Account is deactivated"}), 403
            if user.role not in roles:
                return jsonify({
                    "error": "Access denied",
                    "required_roles": list(roles),
                    "current_role": user.role
                }), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_current_user():
    """Get the current authenticated user."""
    from app.models import User
    identity = get_jwt_identity()
    return User.query.get(identity)


# ============================================================
# Geolocation Utilities
# ============================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on earth using Haversine formula.
    Returns distance in kilometers.
    """
    R = 6371  # Earth's radius in km
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ============================================================
# Pagination Utility
# ============================================================

def paginate_query(query, page: int, per_page: int, max_per_page: int = 100):
    """Paginate a SQLAlchemy query."""
    per_page = min(per_page, max_per_page)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "items": [item.to_dict() for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev
        }
    }


# ============================================================
# Response Helpers
# ============================================================

def success_response(data=None, message="Success", status_code=200):
    """Standard success response."""
    response = {"success": True, "message": message}
    if data is not None:
        response["data"] = data
    return jsonify(response), status_code


def error_response(message="An error occurred", status_code=400, errors=None):
    """Standard error response."""
    response = {"success": False, "error": message}
    if errors:
        response["errors"] = errors
    return jsonify(response), status_code


# ============================================================
# Validation Helpers
# ============================================================

def validate_required_fields(data: dict, required_fields: list) -> list:
    """Check for missing required fields."""
    missing = [field for field in required_fields if not data.get(field)]
    return missing


def sanitize_string(value: str, max_length: int = 255) -> str:
    """Sanitize and truncate a string."""
    if not value:
        return ""
    return str(value).strip()[:max_length]
