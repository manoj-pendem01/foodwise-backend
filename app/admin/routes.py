"""
FoodWise AI - Admin Service & Routes
"""
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from sqlalchemy import func, desc
from app import db
from app.models import User, Restaurant, NGO, FoodListing, FoodRequest, Notification
from app.utils import role_required

admin_bp = Blueprint("admin", __name__)


class AdminService:

    @staticmethod
    def get_platform_stats() -> dict:
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)

        total_users = User.query.count()
        total_restaurants = Restaurant.query.count()
        total_ngos = NGO.query.count()
        total_listings = FoodListing.query.count()
        total_delivered = FoodRequest.query.filter_by(status="delivered").count()
        active_listings = FoodListing.query.filter_by(status="available").count()
        pending_requests = FoodRequest.query.filter_by(status="pending").count()

        # Food saved this month (delivered)
        food_saved = db.session.query(func.sum(FoodListing.quantity)).join(
            FoodRequest, FoodRequest.food_listing_id == FoodListing.id
        ).filter(
            FoodRequest.status == "delivered",
            FoodRequest.delivery_time >= thirty_days_ago
        ).scalar() or 0

        # Daily activity last 30 days
        daily_activity = []
        for i in range(29, -1, -1):
            day = now - timedelta(days=i)
            ds = day.replace(hour=0, minute=0, second=0, microsecond=0)
            de = ds + timedelta(days=1)

            new_listings = FoodListing.query.filter(
                FoodListing.created_at >= ds,
                FoodListing.created_at < de
            ).count()
            new_requests = FoodRequest.query.filter(
                FoodRequest.created_at >= ds,
                FoodRequest.created_at < de
            ).count()
            deliveries = FoodRequest.query.filter(
                FoodRequest.status == "delivered",
                FoodRequest.delivery_time >= ds,
                FoodRequest.delivery_time < de
            ).count()

            daily_activity.append({
                "date": day.strftime("%Y-%m-%d"),
                "listings": new_listings,
                "requests": new_requests,
                "deliveries": deliveries
            })

        # Top donors
        top_donors = db.session.query(
            Restaurant.name,
            func.count(FoodRequest.id).label("donations")
        ).join(FoodRequest, FoodRequest.restaurant_id == Restaurant.id).filter(
            FoodRequest.status == "delivered"
        ).group_by(Restaurant.id).order_by(desc("donations")).limit(5).all()

        # Category breakdown
        category_stats = db.session.query(
            FoodListing.category,
            func.count(FoodListing.id).label("count")
        ).group_by(FoodListing.category).all()

        return {
            "overview": {
                "total_users": total_users,
                "total_restaurants": total_restaurants,
                "total_ngos": total_ngos,
                "total_listings": total_listings,
                "total_delivered": total_delivered,
                "active_listings": active_listings,
                "pending_requests": pending_requests,
                "food_saved_kg_this_month": float(food_saved)
            },
            "daily_activity": daily_activity,
            "top_donors": [{"name": r.name, "donations": r.donations} for r in top_donors],
            "category_breakdown": [{"category": c.category, "count": c.count} for c in category_stats]
        }

    @staticmethod
    def get_all_users(role=None, page=1, per_page=20):
        query = User.query
        if role:
            query = query.filter_by(role=role)
        query = query.order_by(desc(User.created_at))
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        users = []
        for u in pagination.items:
            ud = u.to_dict()
            if u.restaurant:
                ud["profile"] = u.restaurant.to_dict()
            elif u.ngo:
                ud["profile"] = u.ngo.to_dict()
            users.append(ud)
        return {
            "users": users,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages
            }
        }

    @staticmethod
    def toggle_user_status(user_id: int) -> tuple[dict, int]:
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}, 404
        if user.role == "admin":
            return {"error": "Cannot deactivate admin"}, 403
        user.is_active = not user.is_active
        db.session.commit()
        return {"message": f"User {'activated' if user.is_active else 'deactivated'}", "is_active": user.is_active}, 200

    @staticmethod
    def verify_entity(entity_type: str, entity_id: int) -> tuple[dict, int]:
        if entity_type == "restaurant":
            entity = Restaurant.query.get(entity_id)
        elif entity_type == "ngo":
            entity = NGO.query.get(entity_id)
        else:
            return {"error": "Invalid entity type"}, 400
        if not entity:
            return {"error": "Entity not found"}, 404
        entity.is_verified = True
        db.session.commit()
        return {"message": f"{entity_type.capitalize()} verified"}, 200

    @staticmethod
    def get_all_listings(status=None, page=1, per_page=20):
        query = FoodListing.query
        if status:
            query = query.filter_by(status=status)
        query = query.order_by(desc(FoodListing.created_at))
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return {
            "listings": [l.to_dict() for l in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages
            }
        }

    @staticmethod
    def get_all_requests(status=None, page=1, per_page=20):
        query = FoodRequest.query
        if status:
            query = query.filter_by(status=status)
        query = query.order_by(desc(FoodRequest.created_at))
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return {
            "requests": [r.to_dict() for r in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages
            }
        }


# ============================================================
# Admin Routes
# ============================================================

@admin_bp.route("/dashboard", methods=["GET"])
@role_required("admin")
def dashboard():
    result = AdminService.get_platform_stats()
    return jsonify(result), 200


@admin_bp.route("/users", methods=["GET"])
@role_required("admin")
def get_users():
    role = request.args.get("role")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    result = AdminService.get_all_users(role, page, per_page)
    return jsonify(result), 200


@admin_bp.route("/users/<int:user_id>/toggle-status", methods=["POST"])
@role_required("admin")
def toggle_user(user_id):
    result, status = AdminService.toggle_user_status(user_id)
    return jsonify(result), status


@admin_bp.route("/verify/<string:entity_type>/<int:entity_id>", methods=["POST"])
@role_required("admin")
def verify_entity(entity_type, entity_id):
    result, status = AdminService.verify_entity(entity_type, entity_id)
    return jsonify(result), status


@admin_bp.route("/listings", methods=["GET"])
@role_required("admin")
def get_listings():
    status = request.args.get("status")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    result = AdminService.get_all_listings(status, page, per_page)
    return jsonify(result), 200


@admin_bp.route("/requests", methods=["GET"])
@role_required("admin")
def get_requests():
    status = request.args.get("status")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    result = AdminService.get_all_requests(status, page, per_page)
    return jsonify(result), 200


@admin_bp.route("/broadcast", methods=["POST"])
@role_required("admin")
def broadcast_notification():
    from app.notifications.service import NotificationService
    data = request.get_json()
    role = data.get("role")
    title = data.get("title")
    message = data.get("message")

    if not title or not message:
        return jsonify({"error": "Title and message required"}), 400

    query = User.query.filter_by(is_active=True)
    if role:
        query = query.filter_by(role=role)
    users = query.all()

    for user in users:
        NotificationService.send_notification(
            user_id=user.id,
            title=title,
            message=message,
            notif_type="system"
        )

    return jsonify({"message": f"Broadcast sent to {len(users)} users"}), 200
