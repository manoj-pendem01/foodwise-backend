"""
FoodWise AI - SQLAlchemy Models
"""
from datetime import datetime
from app import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum("restaurant", "ngo", "admin"), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    restaurant = db.relationship("Restaurant", back_populates="user", uselist=False, cascade="all, delete-orphan")
    ngo = db.relationship("NGO", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "email_verified": self.email_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }


class Restaurant(db.Model):
    __tablename__ = "restaurants"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(100), nullable=False, index=True)
    state = db.Column(db.String(100))
    zip_code = db.Column(db.String(20))
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    cuisine_type = db.Column(db.String(100))
    seating_capacity = db.Column(db.Integer, default=0)
    avg_daily_covers = db.Column(db.Integer, default=0)
    logo_url = db.Column(db.String(500))
    is_verified = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Numeric(3, 2), default=0.00)
    total_donations = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship("User", back_populates="restaurant")
    food_listings = db.relationship("FoodListing", back_populates="restaurant", cascade="all, delete-orphan")
    food_requests = db.relationship("FoodRequest", back_populates="restaurant", foreign_keys="FoodRequest.restaurant_id")
    food_history = db.relationship("FoodHistory", back_populates="restaurant", cascade="all, delete-orphan")
    waste_predictions = db.relationship("WastePrediction", back_populates="restaurant", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "phone": self.phone,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "latitude": float(self.latitude) if self.latitude else None,
            "longitude": float(self.longitude) if self.longitude else None,
            "cuisine_type": self.cuisine_type,
            "seating_capacity": self.seating_capacity,
            "avg_daily_covers": self.avg_daily_covers,
            "logo_url": self.logo_url,
            "is_verified": self.is_verified,
            "rating": float(self.rating) if self.rating else 0,
            "total_donations": self.total_donations,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class NGO(db.Model):
    __tablename__ = "ngos"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(100), nullable=False, index=True)
    state = db.Column(db.String(100))
    zip_code = db.Column(db.String(20))
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    registration_number = db.Column(db.String(100))
    focus_area = db.Column(db.String(200))
    beneficiaries_count = db.Column(db.Integer, default=0)
    logo_url = db.Column(db.String(500))
    is_verified = db.Column(db.Boolean, default=False)
    total_received = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship("User", back_populates="ngo")
    food_requests = db.relationship("FoodRequest", back_populates="ngo", foreign_keys="FoodRequest.ngo_id")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "phone": self.phone,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "latitude": float(self.latitude) if self.latitude else None,
            "longitude": float(self.longitude) if self.longitude else None,
            "registration_number": self.registration_number,
            "focus_area": self.focus_area,
            "beneficiaries_count": self.beneficiaries_count,
            "logo_url": self.logo_url,
            "is_verified": self.is_verified,
            "total_received": self.total_received,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class FoodListing(db.Model):
    __tablename__ = "food_listings"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.Enum("cooked_meal", "raw_ingredients", "bakery", "dairy", "beverages", "snacks", "other"), default="other")
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    unit = db.Column(db.String(50), default="kg")
    serves_people = db.Column(db.Integer)
    expiry_time = db.Column(db.DateTime, nullable=False, index=True)
    pickup_deadline = db.Column(db.DateTime, nullable=False)
    pickup_instructions = db.Column(db.Text)
    allergens = db.Column(db.Text)
    is_vegetarian = db.Column(db.Boolean, default=False)
    is_vegan = db.Column(db.Boolean, default=False)
    is_halal = db.Column(db.Boolean, default=False)
    status = db.Column(db.Enum("available", "claimed", "in_transit", "delivered", "expired", "cancelled"), default="available", index=True)
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    restaurant = db.relationship("Restaurant", back_populates="food_listings")
    requests = db.relationship("FoodRequest", back_populates="food_listing", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "restaurant_id": self.restaurant_id,
            "restaurant": self.restaurant.to_dict() if self.restaurant else None,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "quantity": float(self.quantity) if self.quantity else 0,
            "unit": self.unit,
            "serves_people": self.serves_people,
            "expiry_time": self.expiry_time.isoformat() if self.expiry_time else None,
            "pickup_deadline": self.pickup_deadline.isoformat() if self.pickup_deadline else None,
            "pickup_instructions": self.pickup_instructions,
            "allergens": self.allergens,
            "is_vegetarian": self.is_vegetarian,
            "is_vegan": self.is_vegan,
            "is_halal": self.is_halal,
            "status": self.status,
            "image_url": self.image_url,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class FoodRequest(db.Model):
    __tablename__ = "food_requests"

    id = db.Column(db.Integer, primary_key=True)
    food_listing_id = db.Column(db.Integer, db.ForeignKey("food_listings.id"), nullable=False)
    ngo_id = db.Column(db.Integer, db.ForeignKey("ngos.id"), nullable=False, index=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    status = db.Column(db.Enum("pending", "accepted", "rejected", "in_transit", "delivered", "cancelled"), default="pending", index=True)
    requested_quantity = db.Column(db.Numeric(10, 2))
    notes = db.Column(db.Text)
    rejection_reason = db.Column(db.Text)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    pickup_time = db.Column(db.DateTime, nullable=True)
    delivery_time = db.Column(db.DateTime, nullable=True)
    distance_km = db.Column(db.Numeric(8, 2))
    match_score = db.Column(db.Numeric(5, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    food_listing = db.relationship("FoodListing", back_populates="requests")
    ngo = db.relationship("NGO", back_populates="food_requests", foreign_keys=[ngo_id])
    restaurant = db.relationship("Restaurant", back_populates="food_requests", foreign_keys=[restaurant_id])
    tracking = db.relationship("DeliveryTracking", back_populates="request", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "food_listing_id": self.food_listing_id,
            "food_listing": self.food_listing.to_dict() if self.food_listing else None,
            "ngo_id": self.ngo_id,
            "ngo": self.ngo.to_dict() if self.ngo else None,
            "restaurant_id": self.restaurant_id,
            "restaurant": self.restaurant.to_dict() if self.restaurant else None,
            "status": self.status,
            "requested_quantity": float(self.requested_quantity) if self.requested_quantity else None,
            "notes": self.notes,
            "rejection_reason": self.rejection_reason,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "pickup_time": self.pickup_time.isoformat() if self.pickup_time else None,
            "delivery_time": self.delivery_time.isoformat() if self.delivery_time else None,
            "distance_km": float(self.distance_km) if self.distance_km else None,
            "match_score": float(self.match_score) if self.match_score else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class DeliveryTracking(db.Model):
    __tablename__ = "delivery_tracking"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("food_requests.id"), nullable=False, index=True)
    latitude = db.Column(db.Numeric(10, 8), nullable=False)
    longitude = db.Column(db.Numeric(11, 8), nullable=False)
    status = db.Column(db.String(100))
    notes = db.Column(db.Text)
    tracked_at = db.Column(db.DateTime, default=datetime.utcnow)

    request = db.relationship("FoodRequest", back_populates="tracking")

    def to_dict(self):
        return {
            "id": self.id,
            "request_id": self.request_id,
            "latitude": float(self.latitude),
            "longitude": float(self.longitude),
            "status": self.status,
            "notes": self.notes,
            "tracked_at": self.tracked_at.isoformat()
        }


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.Enum("food_available", "request_accepted", "request_rejected", "pickup_reminder", "delivery_confirmed", "system", "waste_alert"), default="system")
    is_read = db.Column(db.Boolean, default=False, index=True)
    related_id = db.Column(db.Integer)
    related_type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="notifications")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "type": self.type,
            "is_read": self.is_read,
            "related_id": self.related_id,
            "related_type": self.related_type,
            "created_at": self.created_at.isoformat()
        }


class WastePrediction(db.Model):
    __tablename__ = "waste_predictions"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    prediction_date = db.Column(db.Date, nullable=False)
    predicted_waste_kg = db.Column(db.Numeric(8, 2), nullable=False)
    actual_waste_kg = db.Column(db.Numeric(8, 2))
    confidence_score = db.Column(db.Numeric(5, 4))
    factors = db.Column(db.JSON)
    suggestions = db.Column(db.JSON)
    model_version = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    restaurant = db.relationship("Restaurant", back_populates="waste_predictions")

    def to_dict(self):
        return {
            "id": self.id,
            "restaurant_id": self.restaurant_id,
            "prediction_date": self.prediction_date.isoformat() if self.prediction_date else None,
            "predicted_waste_kg": float(self.predicted_waste_kg) if self.predicted_waste_kg else 0,
            "actual_waste_kg": float(self.actual_waste_kg) if self.actual_waste_kg else None,
            "confidence_score": float(self.confidence_score) if self.confidence_score else None,
            "factors": self.factors,
            "suggestions": self.suggestions,
            "model_version": self.model_version,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class FoodHistory(db.Model):
    __tablename__ = "food_history"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    record_date = db.Column(db.Date, nullable=False, index=True)
    day_of_week = db.Column(db.SmallInteger, nullable=False)
    is_holiday = db.Column(db.Boolean, default=False)
    weather_condition = db.Column(db.String(50))
    temperature_celsius = db.Column(db.Numeric(5, 2))
    covers_served = db.Column(db.Integer, default=0)
    food_prepared_kg = db.Column(db.Numeric(8, 2), nullable=False)
    food_donated_kg = db.Column(db.Numeric(8, 2), default=0)
    food_wasted_kg = db.Column(db.Numeric(8, 2), default=0)
    revenue = db.Column(db.Numeric(10, 2), default=0)
    special_event = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    restaurant = db.relationship("Restaurant", back_populates="food_history")

    def to_dict(self):
        return {
            "id": self.id,
            "restaurant_id": self.restaurant_id,
            "record_date": self.record_date.isoformat() if self.record_date else None,
            "day_of_week": self.day_of_week,
            "is_holiday": self.is_holiday,
            "weather_condition": self.weather_condition,
            "temperature_celsius": float(self.temperature_celsius) if self.temperature_celsius else None,
            "covers_served": self.covers_served,
            "food_prepared_kg": float(self.food_prepared_kg) if self.food_prepared_kg else 0,
            "food_donated_kg": float(self.food_donated_kg) if self.food_donated_kg else 0,
            "food_wasted_kg": float(self.food_wasted_kg) if self.food_wasted_kg else 0,
            "revenue": float(self.revenue) if self.revenue else 0,
            "special_event": self.special_event,
            "notes": self.notes
        }
