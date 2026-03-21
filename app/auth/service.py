"""
FoodWise AI - Authentication Service
"""
from datetime import datetime
from flask_jwt_extended import create_access_token, create_refresh_token
from app import db
from app.models import User, Restaurant, NGO
from app.utils import hash_password, verify_password, validate_password, validate_email


class AuthService:

    @staticmethod
    def register(data: dict) -> tuple[dict, int]:
        """Register a new user with profile."""
        email = data.get("email", "").lower().strip()
        password = data.get("password", "")
        role = data.get("role", "")
        profile = data.get("profile", {})

        # Validations
        if not email or not password or not role:
            return {"error": "Email, password, and role are required"}, 400

        if role not in ["restaurant", "ngo"]:
            return {"error": "Role must be 'restaurant' or 'ngo'"}, 400

        if not validate_email(email):
            return {"error": "Invalid email format"}, 400

        valid_pw, pw_msg = validate_password(password)
        if not valid_pw:
            return {"error": pw_msg}, 400

        if User.query.filter_by(email=email).first():
            return {"error": "Email already registered"}, 409

        # Validate profile required fields
        required_profile = ["name", "phone", "address", "city", "latitude", "longitude"]
        missing = [f for f in required_profile if not profile.get(f)]
        if missing:
            return {"error": f"Missing profile fields: {', '.join(missing)}"}, 400

        try:
            # Create user
            user = User(
                email=email,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
                email_verified=True  # Skip email verification for now
            )
            db.session.add(user)
            db.session.flush()  # Get user.id before commit

            # Create profile
            if role == "restaurant":
                restaurant = Restaurant(
                    user_id=user.id,
                    name=profile.get("name"),
                    description=profile.get("description"),
                    phone=profile.get("phone"),
                    address=profile.get("address"),
                    city=profile.get("city"),
                    state=profile.get("state"),
                    zip_code=profile.get("zip_code"),
                    latitude=float(profile.get("latitude")),
                    longitude=float(profile.get("longitude")),
                    cuisine_type=profile.get("cuisine_type"),
                    seating_capacity=int(profile.get("seating_capacity", 0)),
                    avg_daily_covers=int(profile.get("avg_daily_covers", 0))
                )
                db.session.add(restaurant)

            elif role == "ngo":
                ngo = NGO(
                    user_id=user.id,
                    name=profile.get("name"),
                    description=profile.get("description"),
                    phone=profile.get("phone"),
                    address=profile.get("address"),
                    city=profile.get("city"),
                    state=profile.get("state"),
                    zip_code=profile.get("zip_code"),
                    latitude=float(profile.get("latitude")),
                    longitude=float(profile.get("longitude")),
                    registration_number=profile.get("registration_number"),
                    focus_area=profile.get("focus_area"),
                    beneficiaries_count=int(profile.get("beneficiaries_count", 0))
                )
                db.session.add(ngo)

            db.session.commit()

            # Generate tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)

            return {
                "message": "Registration successful",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": user.to_dict()
            }, 201

        except Exception as e:
            db.session.rollback()
            return {"error": f"Registration failed: {str(e)}"}, 500

    @staticmethod
    def login(email: str, password: str) -> tuple[dict, int]:
        """Authenticate user and return tokens."""
        if not email or not password:
            return {"error": "Email and password are required"}, 400

        email = email.lower().strip()
        user = User.query.filter_by(email=email).first()

        if not user or not verify_password(password, user.password_hash):
            return {"error": "Invalid email or password"}, 401

        if not user.is_active:
            return {"error": "Account is deactivated. Contact support."}, 403

        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Build profile data
        profile = None
        if user.role == "restaurant" and user.restaurant:
            profile = user.restaurant.to_dict()
        elif user.role == "ngo" and user.ngo:
            profile = user.ngo.to_dict()

        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {**user.to_dict(), "profile": profile}
        }, 200

    @staticmethod
    def get_profile(user_id: int) -> tuple[dict, int]:
        """Get full user profile."""
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}, 404

        profile = None
        if user.role == "restaurant" and user.restaurant:
            profile = user.restaurant.to_dict()
        elif user.role == "ngo" and user.ngo:
            profile = user.ngo.to_dict()

        return {"user": {**user.to_dict(), "profile": profile}}, 200

    @staticmethod
    def change_password(user_id: int, current_password: str, new_password: str) -> tuple[dict, int]:
        """Change user password."""
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}, 404

        if not verify_password(current_password, user.password_hash):
            return {"error": "Current password is incorrect"}, 400

        valid_pw, pw_msg = validate_password(new_password)
        if not valid_pw:
            return {"error": pw_msg}, 400

        user.password_hash = hash_password(new_password)
        db.session.commit()
        return {"message": "Password updated successfully"}, 200
