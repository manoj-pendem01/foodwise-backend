"""
FoodWise AI - Restaurant Routes
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils import role_required
from app.restaurant.service import RestaurantService
from app.models import Restaurant

restaurant_bp = Blueprint("restaurant", __name__)


def get_restaurant_id():
    from app.utils import get_current_user
    user = get_current_user()
    if user and user.restaurant:
        return user.restaurant.id
    return None


@restaurant_bp.route("/listings", methods=["GET"])
@role_required("restaurant")
def get_listings():
    rid = get_restaurant_id()
    if not rid:
        return jsonify({"error": "Restaurant profile not found"}), 404
    status = request.args.get("status")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    result = RestaurantService.get_listings(rid, status, page, per_page)
    return jsonify(result), 200


@restaurant_bp.route("/listings", methods=["POST"])
@role_required("restaurant")
def add_listing():
    rid = get_restaurant_id()
    if not rid:
        return jsonify({"error": "Restaurant profile not found"}), 404
    data = request.get_json()
    result, status = RestaurantService.add_food_listing(rid, data)
    return jsonify(result), status


@restaurant_bp.route("/listings/<int:listing_id>", methods=["PUT"])
@role_required("restaurant")
def update_listing(listing_id):
    rid = get_restaurant_id()
    data = request.get_json()
    result, status = RestaurantService.update_listing(listing_id, rid, data)
    return jsonify(result), status


@restaurant_bp.route("/listings/<int:listing_id>", methods=["DELETE"])
@role_required("restaurant")
def cancel_listing(listing_id):
    rid = get_restaurant_id()
    result, status = RestaurantService.cancel_listing(listing_id, rid)
    return jsonify(result), status


@restaurant_bp.route("/requests", methods=["GET"])
@role_required("restaurant")
def get_requests():
    rid = get_restaurant_id()
    status = request.args.get("status")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    result = RestaurantService.get_requests(rid, status, page, per_page)
    return jsonify(result), 200


@restaurant_bp.route("/requests/<int:request_id>/respond", methods=["POST"])
@role_required("restaurant")
def respond_to_request(request_id):
    rid = get_restaurant_id()
    data = request.get_json()
    result, status = RestaurantService.respond_to_request(
        request_id, rid,
        data.get("action"),
        data.get("reason")
    )
    return jsonify(result), status


@restaurant_bp.route("/dashboard", methods=["GET"])
@role_required("restaurant")
def dashboard():
    rid = get_restaurant_id()
    if not rid:
        return jsonify({"error": "Restaurant profile not found"}), 404
    result = RestaurantService.get_dashboard_analytics(rid)
    return jsonify(result), 200


@restaurant_bp.route("/history", methods=["POST"])
@role_required("restaurant")
def add_history():
    rid = get_restaurant_id()
    data = request.get_json()
    result, status = RestaurantService.add_food_history(rid, data)
    return jsonify(result), status


@restaurant_bp.route("/history", methods=["GET"])
@role_required("restaurant")
def get_history():
    rid = get_restaurant_id()
    from app.models import FoodHistory
    from sqlalchemy import desc
    records = FoodHistory.query.filter_by(restaurant_id=rid).order_by(desc(FoodHistory.record_date)).limit(30).all()
    return jsonify({"history": [r.to_dict() for r in records]}), 200


@restaurant_bp.route("/profile", methods=["GET"])
@role_required("restaurant")
def get_profile():
    rid = get_restaurant_id()
    restaurant = Restaurant.query.get(rid)
    if not restaurant:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"restaurant": restaurant.to_dict()}), 200


@restaurant_bp.route("/mark-delivered/<int:request_id>", methods=["POST"])
@role_required("restaurant")
def mark_delivered(request_id):
    rid = get_restaurant_id()
    from app.models import FoodRequest
    from app import db
    req = FoodRequest.query.filter_by(id=request_id, restaurant_id=rid).first()
    if not req:
        return jsonify({"error": "Request not found"}), 404
    from datetime import datetime
    req.status = "delivered"
    req.delivery_time = datetime.utcnow()
    req.food_listing.status = "delivered"
    db.session.commit()
    return jsonify({"message": "Marked as delivered", "request": req.to_dict()}), 200
