"""
FoodWise AI - NGO Service
"""
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_
from app import db
from app.models import FoodListing, FoodRequest, NGO, Restaurant, DeliveryTracking
from app.utils import haversine_distance


class NGOService:

    @staticmethod
    def get_available_food(ngo_id: int, filters: dict = None) -> dict:
        """Get available food listings near the NGO."""
        ngo = NGO.query.get(ngo_id)
        if not ngo:
            return {"error": "NGO not found"}, 404

        max_distance = float(filters.get("max_distance", 25)) if filters else 25
        category = filters.get("category") if filters else None
        is_vegetarian = filters.get("is_vegetarian") if filters else None

        # Get all available listings
        query = FoodListing.query.filter(
            FoodListing.status == "available",
            FoodListing.expiry_time > datetime.utcnow()
        )

        if category:
            query = query.filter_by(category=category)
        if is_vegetarian:
            query = query.filter_by(is_vegetarian=True)

        listings = query.all()

        # Filter by distance and add distance info
        nearby_listings = []
        for listing in listings:
            if listing.restaurant:
                distance = haversine_distance(
                    float(ngo.latitude), float(ngo.longitude),
                    float(listing.restaurant.latitude), float(listing.restaurant.longitude)
                )
                if distance <= max_distance:
                    listing_dict = listing.to_dict()
                    listing_dict["distance_km"] = round(distance, 2)
                    listing_dict["time_remaining_minutes"] = int(
                        (listing.expiry_time - datetime.utcnow()).total_seconds() / 60
                    )
                    # Check if NGO already requested this
                    existing_request = FoodRequest.query.filter_by(
                        food_listing_id=listing.id,
                        ngo_id=ngo_id
                    ).first()
                    listing_dict["already_requested"] = existing_request is not None
                    listing_dict["existing_request_status"] = existing_request.status if existing_request else None
                    nearby_listings.append(listing_dict)

        # Sort by distance
        nearby_listings.sort(key=lambda x: x["distance_km"])
        return {"listings": nearby_listings, "total": len(nearby_listings)}

    @staticmethod
    def request_food(ngo_id: int, listing_id: int, data: dict) -> tuple[dict, int]:
        """Submit a food request for a listing."""
        ngo = NGO.query.get(ngo_id)
        listing = FoodListing.query.get(listing_id)

        if not listing:
            return {"error": "Food listing not found"}, 404
        if listing.status != "available":
            return {"error": "Food listing is no longer available"}, 400
        if listing.expiry_time <= datetime.utcnow():
            return {"error": "Food listing has expired"}, 400

        # Check duplicate request
        existing = FoodRequest.query.filter_by(
            food_listing_id=listing_id,
            ngo_id=ngo_id
        ).first()
        if existing:
            return {"error": "You have already requested this item"}, 409

        # Calculate distance
        distance = haversine_distance(
            float(ngo.latitude), float(ngo.longitude),
            float(listing.restaurant.latitude), float(listing.restaurant.longitude)
        )

        try:
            food_req = FoodRequest(
                food_listing_id=listing_id,
                ngo_id=ngo_id,
                restaurant_id=listing.restaurant_id,
                requested_quantity=data.get("requested_quantity"),
                notes=data.get("notes"),
                distance_km=round(distance, 2)
            )
            db.session.add(food_req)
            db.session.commit()

            # Notify restaurant
            from app.notifications.service import NotificationService
            NotificationService.send_notification(
                user_id=listing.restaurant.user_id,
                title="New Food Request 🔔",
                message=f"{ngo.name} has requested '{listing.title}'. Please respond within 30 minutes.",
                notif_type="food_available",
                related_id=food_req.id,
                related_type="food_request"
            )

            return {"message": "Request submitted successfully", "request": food_req.to_dict()}, 201

        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500

    @staticmethod
    def get_my_requests(ngo_id: int, status: str = None, page: int = 1, per_page: int = 20) -> dict:
        """Get all requests made by this NGO."""
        query = FoodRequest.query.filter_by(ngo_id=ngo_id)
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

    @staticmethod
    def cancel_request(request_id: int, ngo_id: int) -> tuple[dict, int]:
        """Cancel an NGO's food request."""
        req = FoodRequest.query.filter_by(id=request_id, ngo_id=ngo_id).first()
        if not req:
            return {"error": "Request not found"}, 404
        if req.status in ["delivered", "cancelled"]:
            return {"error": "Cannot cancel this request"}, 400

        req.status = "cancelled"
        if req.food_listing.status == "claimed":
            req.food_listing.status = "available"
        db.session.commit()
        return {"message": "Request cancelled"}, 200

    @staticmethod
    def update_pickup_status(request_id: int, ngo_id: int, status: str, lat: float = None, lng: float = None) -> tuple[dict, int]:
        """Update pickup/delivery status with optional location."""
        req = FoodRequest.query.filter_by(id=request_id, ngo_id=ngo_id).first()
        if not req:
            return {"error": "Request not found"}, 404

        valid_transitions = {
            "accepted": ["in_transit"],
            "in_transit": ["delivered"]
        }

        if req.status not in valid_transitions or status not in valid_transitions.get(req.status, []):
            return {"error": f"Cannot transition from {req.status} to {status}"}, 400

        req.status = status
        if status == "in_transit":
            req.pickup_time = datetime.utcnow()
            req.food_listing.status = "in_transit"
        elif status == "delivered":
            req.delivery_time = datetime.utcnow()
            req.food_listing.status = "delivered"
            # Update NGO stats
            ngo = NGO.query.get(ngo_id)
            if ngo:
                ngo.total_received += 1

        # Add tracking point
        if lat and lng:
            tracking = DeliveryTracking(
                request_id=request_id,
                latitude=lat,
                longitude=lng,
                status=status
            )
            db.session.add(tracking)

        db.session.commit()
        return {"message": f"Status updated to {status}", "request": req.to_dict()}, 200

    @staticmethod
    def get_tracking(request_id: int, ngo_id: int) -> tuple[dict, int]:
        """Get delivery tracking history for a request."""
        req = FoodRequest.query.filter_by(id=request_id, ngo_id=ngo_id).first()
        if not req:
            return {"error": "Request not found"}, 404

        tracking = DeliveryTracking.query.filter_by(
            request_id=request_id
        ).order_by(DeliveryTracking.tracked_at).all()

        return {
            "request": req.to_dict(),
            "tracking": [t.to_dict() for t in tracking]
        }, 200

    @staticmethod
    def get_dashboard_analytics(ngo_id: int) -> dict:
        """Get NGO dashboard analytics."""
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)

        total_requests = FoodRequest.query.filter_by(ngo_id=ngo_id).count()
        accepted = FoodRequest.query.filter_by(ngo_id=ngo_id, status="accepted").count()
        delivered = FoodRequest.query.filter_by(ngo_id=ngo_id, status="delivered").count()
        pending = FoodRequest.query.filter_by(ngo_id=ngo_id, status="pending").count()
        in_transit = FoodRequest.query.filter_by(ngo_id=ngo_id, status="in_transit").count()

        # Food received this month
        received_this_month = db.session.query(func.sum(FoodListing.quantity)).join(
            FoodRequest, FoodRequest.food_listing_id == FoodListing.id
        ).filter(
            FoodRequest.ngo_id == ngo_id,
            FoodRequest.status == "delivered",
            FoodRequest.delivery_time >= thirty_days_ago
        ).scalar() or 0

        # Weekly activity
        weekly_data = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            requests_count = FoodRequest.query.filter(
                FoodRequest.ngo_id == ngo_id,
                FoodRequest.created_at >= day_start,
                FoodRequest.created_at < day_end
            ).count()

            delivered_count = FoodRequest.query.filter(
                FoodRequest.ngo_id == ngo_id,
                FoodRequest.status == "delivered",
                FoodRequest.delivery_time >= day_start,
                FoodRequest.delivery_time < day_end
            ).count()

            weekly_data.append({
                "date": day.strftime("%Y-%m-%d"),
                "day": day.strftime("%a"),
                "requests": requests_count,
                "delivered": delivered_count
            })

        recent_requests = FoodRequest.query.filter_by(
            ngo_id=ngo_id
        ).order_by(desc(FoodRequest.created_at)).limit(5).all()

        return {
            "overview": {
                "total_requests": total_requests,
                "accepted": accepted,
                "delivered": delivered,
                "pending": pending,
                "in_transit": in_transit,
                "received_this_month_kg": float(received_this_month)
            },
            "weekly_chart": weekly_data,
            "recent_requests": [r.to_dict() for r in recent_requests]
        }
