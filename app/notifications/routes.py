"""
FoodWise AI - Notification Routes
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.notifications.service import NotificationService

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route("/", methods=["GET"])
@jwt_required()
def get_notifications():
    user_id = get_jwt_identity()
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    result = NotificationService.get_user_notifications(user_id, unread_only, page, per_page)
    return jsonify(result), 200


@notifications_bp.route("/<int:notif_id>/read", methods=["PUT"])
@jwt_required()
def mark_read(notif_id):
    user_id = get_jwt_identity()
    result, status = NotificationService.mark_read(notif_id, user_id)
    return jsonify(result), status


@notifications_bp.route("/read-all", methods=["PUT"])
@jwt_required()
def mark_all_read():
    user_id = get_jwt_identity()
    result = NotificationService.mark_all_read(user_id)
    return jsonify(result), 200


@notifications_bp.route("/unread-count", methods=["GET"])
@jwt_required()
def unread_count():
    from app.models import Notification
    user_id = get_jwt_identity()
    count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
    return jsonify({"unread_count": count}), 200
