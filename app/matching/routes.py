"""
FoodWise AI - Matching Routes
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.utils import role_required, get_current_user
from app.matching.service import MatchingService

matching_bp = Blueprint("matching", __name__)


@matching_bp.route("/find/<int:listing_id>", methods=["GET"])
@role_required("restaurant", "admin")
def find_matches(listing_id):
    """Find matching NGOs for a food listing."""
    matches = MatchingService.find_matching_ngos(listing_id)
    return jsonify({"matches": matches, "total": len(matches)}), 200


@matching_bp.route("/nearby", methods=["GET"])
@role_required("ngo")
def get_nearby():
    """Get nearby food for current NGO using matching algorithm."""
    user = get_current_user()
    if not user or not user.ngo:
        return jsonify({"error": "NGO profile not found"}), 404
    max_dist = float(request.args.get("max_distance", 25))
    matches = MatchingService.get_nearby_food_for_ngo(user.ngo.id, max_dist)
    return jsonify({"matches": matches, "total": len(matches)}), 200


@matching_bp.route("/run", methods=["POST"])
@role_required("admin")
def run_matching():
    """Manually trigger auto-matching (admin only)."""
    MatchingService.run_auto_matching()
    return jsonify({"message": "Auto-matching completed"}), 200
