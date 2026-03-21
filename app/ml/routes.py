"""
FoodWise AI - ML Routes
"""
from flask import Blueprint, request, jsonify
from app.utils import role_required, get_current_user
from app.ml.service import MLService

ml_bp = Blueprint("ml", __name__)


def get_restaurant_id():
    user = get_current_user()
    return user.restaurant.id if user and user.restaurant else None


@ml_bp.route("/train", methods=["POST"])
@role_required("restaurant")
def train_model():
    rid = get_restaurant_id()
    if not rid:
        return jsonify({"error": "Restaurant profile required"}), 404
    result, status = MLService.train_for_restaurant(rid)
    return jsonify(result), status


@ml_bp.route("/predict", methods=["POST"])
@role_required("restaurant")
def predict():
    rid = get_restaurant_id()
    if not rid:
        return jsonify({"error": "Restaurant profile required"}), 404
    data = request.get_json() or {}
    result, status = MLService.predict_waste(
        rid,
        data.get("prediction_date"),
        data.get("input_data", {})
    )
    return jsonify(result), status


@ml_bp.route("/predictions", methods=["GET"])
@role_required("restaurant")
def prediction_history():
    rid = get_restaurant_id()
    days = int(request.args.get("days", 30))
    result = MLService.get_prediction_history(rid, days)
    return jsonify(result), 200


@ml_bp.route("/insights", methods=["GET"])
@role_required("restaurant")
def insights():
    rid = get_restaurant_id()
    if not rid:
        return jsonify({"error": "Restaurant profile required"}), 404
    result = MLService.get_waste_insights(rid)
    return jsonify(result), 200
