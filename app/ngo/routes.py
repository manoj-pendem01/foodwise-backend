"""
FoodWise AI - NGO Routes
"""
from flask import Blueprint, request, jsonify
from app.utils import role_required, get_current_user
from app.ngo.service import NGOService

ngo_bp = Blueprint("ngo", __name__)


def get_ngo_id():
    user = get_current_user()
    if user and user.ngo:
        return user.ngo.id
    return None


@ngo_bp.route("/food/available", methods=["GET"])
@role_required("ngo")
def get_available_food():
    ngo_id = get_ngo_id()
    if not ngo_id:
        return jsonify({"error": "NGO profile not found"}), 404
    filters = {
        "max_distance": request.args.get("max_distance", 25),
        "category": request.args.get("category"),
        "is_vegetarian": request.args.get("is_vegetarian")
    }
    result = NGOService.get_available_food(ngo_id, filters)
    return jsonify(result), 200


@ngo_bp.route("/food/<int:listing_id>/request", methods=["POST"])
@role_required("ngo")
def request_food(listing_id):
    ngo_id = get_ngo_id()
    if not ngo_id:
        return jsonify({"error": "NGO profile not found"}), 404
    data = request.get_json() or {}
    result, status = NGOService.request_food(ngo_id, listing_id, data)
    return jsonify(result), status


@ngo_bp.route("/requests", methods=["GET"])
@role_required("ngo")
def get_my_requests():
    ngo_id = get_ngo_id()
    status = request.args.get("status")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    result = NGOService.get_my_requests(ngo_id, status, page, per_page)
    return jsonify(result), 200


@ngo_bp.route("/requests/<int:request_id>/cancel", methods=["POST"])
@role_required("ngo")
def cancel_request(request_id):
    ngo_id = get_ngo_id()
    result, status = NGOService.cancel_request(request_id, ngo_id)
    return jsonify(result), status


@ngo_bp.route("/requests/<int:request_id>/status", methods=["PUT"])
@role_required("ngo")
def update_status(request_id):
    ngo_id = get_ngo_id()
    data = request.get_json()
    result, status = NGOService.update_pickup_status(
        request_id, ngo_id,
        data.get("status"),
        data.get("latitude"),
        data.get("longitude")
    )
    return jsonify(result), status


@ngo_bp.route("/requests/<int:request_id>/tracking", methods=["GET"])
@role_required("ngo")
def get_tracking(request_id):
    ngo_id = get_ngo_id()
    result, status = NGOService.get_tracking(request_id, ngo_id)
    return jsonify(result), status


@ngo_bp.route("/dashboard", methods=["GET"])
@role_required("ngo")
def dashboard():
    ngo_id = get_ngo_id()
    if not ngo_id:
        return jsonify({"error": "NGO profile not found"}), 404
    result = NGOService.get_dashboard_analytics(ngo_id)
    return jsonify(result), 200


@ngo_bp.route("/profile", methods=["GET"])
@role_required("ngo")
def get_profile():
    from app.models import NGO
    ngo_id = get_ngo_id()
    ngo = NGO.query.get(ngo_id)
    return jsonify({"ngo": ngo.to_dict()}), 200
