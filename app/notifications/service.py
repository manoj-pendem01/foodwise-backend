"""
FoodWise AI - Notification Service
"""
from datetime import datetime, timedelta
from app import db
from app.models import Notification, FoodListing, NGO


class NotificationService:

    @staticmethod
    def send_notification(user_id: int, title: str, message: str,
                          notif_type: str = "system", related_id: int = None,
                          related_type: str = None) -> Notification:
        """Create and store a notification."""
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notif_type,
            related_id=related_id,
            related_type=related_type
        )
        db.session.add(notif)
        db.session.commit()
        return notif

    @staticmethod
    def notify_ngos_new_food(listing: FoodListing) -> None:
        """Notify all NGOs in range about a new food listing."""
        from app.utils import haversine_distance
        all_ngos = NGO.query.filter_by(is_verified=True).all()
        max_dist = 25  # km

        for ngo in all_ngos:
            distance = haversine_distance(
                float(listing.restaurant.latitude), float(listing.restaurant.longitude),
                float(ngo.latitude), float(ngo.longitude)
            )
            if distance <= max_dist:
                NotificationService.send_notification(
                    user_id=ngo.user_id,
                    title=f"New Food Available! ({round(distance, 1)} km away)",
                    message=f"{listing.restaurant.name} has listed '{listing.title}' - {listing.quantity}{listing.unit}. Expires: {listing.expiry_time.strftime('%H:%M')}",
                    notif_type="food_available",
                    related_id=listing.id,
                    related_type="food_listing"
                )

    @staticmethod
    def send_expiry_alerts() -> None:
        """Send alerts for food listings expiring soon."""
        two_hours_from_now = datetime.utcnow() + timedelta(hours=2)
        expiring_soon = FoodListing.query.filter(
            FoodListing.status == "available",
            FoodListing.expiry_time <= two_hours_from_now,
            FoodListing.expiry_time > datetime.utcnow()
        ).all()

        for listing in expiring_soon:
            # Alert restaurant
            NotificationService.send_notification(
                user_id=listing.restaurant.user_id,
                title="⚠️ Food Expiring Soon",
                message=f"'{listing.title}' expires in less than 2 hours and hasn't been claimed yet!",
                notif_type="waste_alert",
                related_id=listing.id,
                related_type="food_listing"
            )

    @staticmethod
    def get_user_notifications(user_id: int, unread_only: bool = False, page: int = 1, per_page: int = 20) -> dict:
        """Get paginated notifications for a user."""
        query = Notification.query.filter_by(user_id=user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        query = query.order_by(Notification.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        unread_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()

        return {
            "notifications": [n.to_dict() for n in pagination.items],
            "unread_count": unread_count,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages
            }
        }

    @staticmethod
    def mark_read(notification_id: int, user_id: int) -> tuple[dict, int]:
        notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if not notif:
            return {"error": "Notification not found"}, 404
        notif.is_read = True
        db.session.commit()
        return {"message": "Marked as read"}, 200

    @staticmethod
    def mark_all_read(user_id: int) -> dict:
        Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
        db.session.commit()
        return {"message": "All notifications marked as read"}
