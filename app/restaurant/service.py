"""
FoodWise AI - Restaurant Service
"""
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from app import db
from app.models import FoodListing, FoodRequest, FoodHistory, WastePrediction, Restaurant


class RestaurantService:

    @staticmethod
    def add_food_listing(restaurant_id: int, data: dict) -> tuple[dict, int]:
        """Add a new food surplus listing."""
        required = ["title", "quantity", "expiry_time", "pickup_deadline"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return {"error": f"Missing fields: {', '.join(missing)}"}, 400

        try:
            expiry = datetime.fromisoformat(data["expiry_time"].replace("Z", "+00:00"))
            pickup = datetime.fromisoformat(data["pickup_deadline"].replace("Z", "+00:00"))

            if expiry <= datetime.utcnow():
                return {"error": "Expiry time must be in the future"}, 400
            if pickup > expiry:
                return {"error": "Pickup deadline must be before expiry time"}, 400

            listing = FoodListing(
                restaurant_id=restaurant_id,
                title=data["title"],
                description=data.get("description"),
                category=data.get("category", "other"),
                quantity=float(data["quantity"]),
                unit=data.get("unit", "kg"),
                serves_people=data.get("serves_people"),
                expiry_time=expiry,
                pickup_deadline=pickup,
                pickup_instructions=data.get("pickup_instructions"),
                allergens=data.get("allergens"),
                is_vegetarian=bool(data.get("is_vegetarian", False)),
                is_vegan=bool(data.get("is_vegan", False)),
                is_halal=bool(data.get("is_halal", False)),
                image_url=data.get("image_url")
            )
            db.session.add(listing)

            # Update restaurant donation count
            restaurant = Restaurant.query.get(restaurant_id)
            if restaurant:
                restaurant.total_donations += 1

            db.session.commit()

            # Trigger matching
            from app.matching.service import MatchingService
            MatchingService.match_listing(listing.id)

            # Notify nearby NGOs
            from app.notifications.service import NotificationService
            NotificationService.notify_ngos_new_food(listing)

            return {"message": "Food listing created", "listing": listing.to_dict()}, 201

        except ValueError as e:
            return {"error": f"Invalid data: {str(e)}"}, 400
        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500

    @staticmethod
    def get_listings(restaurant_id: int, status: str = None, page: int = 1, per_page: int = 20) -> dict:
        """Get paginated food listings for a restaurant."""
        query = FoodListing.query.filter_by(restaurant_id=restaurant_id)
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
    def update_listing(listing_id: int, restaurant_id: int, data: dict) -> tuple[dict, int]:
        """Update a food listing."""
        listing = FoodListing.query.filter_by(id=listing_id, restaurant_id=restaurant_id).first()
        if not listing:
            return {"error": "Listing not found"}, 404
        if listing.status not in ["available"]:
            return {"error": "Cannot edit a claimed or delivered listing"}, 400

        updatable = ["title", "description", "quantity", "unit", "serves_people",
                     "pickup_instructions", "allergens", "is_vegetarian", "is_vegan",
                     "is_halal", "category", "image_url"]
        for field in updatable:
            if field in data:
                setattr(listing, field, data[field])

        if "expiry_time" in data:
            listing.expiry_time = datetime.fromisoformat(data["expiry_time"].replace("Z", "+00:00"))
        if "pickup_deadline" in data:
            listing.pickup_deadline = datetime.fromisoformat(data["pickup_deadline"].replace("Z", "+00:00"))

        db.session.commit()
        return {"message": "Listing updated", "listing": listing.to_dict()}, 200

    @staticmethod
    def cancel_listing(listing_id: int, restaurant_id: int) -> tuple[dict, int]:
        """Cancel a food listing."""
        listing = FoodListing.query.filter_by(id=listing_id, restaurant_id=restaurant_id).first()
        if not listing:
            return {"error": "Listing not found"}, 404
        if listing.status in ["delivered", "cancelled"]:
            return {"error": "Listing cannot be cancelled"}, 400

        listing.status = "cancelled"
        # Cancel pending requests
        FoodRequest.query.filter_by(food_listing_id=listing_id, status="pending").update({"status": "cancelled"})
        db.session.commit()
        return {"message": "Listing cancelled"}, 200

    @staticmethod
    def get_requests(restaurant_id: int, status: str = None, page: int = 1, per_page: int = 20) -> dict:
        """Get incoming requests for the restaurant."""
        query = FoodRequest.query.filter_by(restaurant_id=restaurant_id)
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
    def respond_to_request(request_id: int, restaurant_id: int, action: str, reason: str = None) -> tuple[dict, int]:
        """Accept or reject a food request."""
        req = FoodRequest.query.filter_by(id=request_id, restaurant_id=restaurant_id).first()
        if not req:
            return {"error": "Request not found"}, 404
        if req.status != "pending":
            return {"error": "Request is not in pending status"}, 400
        if action not in ["accept", "reject"]:
            return {"error": "Action must be 'accept' or 'reject'"}, 400

        req.responded_at = datetime.utcnow()

        if action == "accept":
            req.status = "accepted"
            req.food_listing.status = "claimed"
            # Notify NGO
            from app.notifications.service import NotificationService
            NotificationService.send_notification(
                user_id=req.ngo.user_id,
                title="Request Accepted! 🎉",
                message=f"Your request for '{req.food_listing.title}' has been accepted. Please proceed for pickup.",
                notif_type="request_accepted",
                related_id=req.id,
                related_type="food_request"
            )
        else:
            req.status = "rejected"
            req.rejection_reason = reason
            from app.notifications.service import NotificationService
            NotificationService.send_notification(
                user_id=req.ngo.user_id,
                title="Request Update",
                message=f"Your request for '{req.food_listing.title}' was not accepted. Reason: {reason or 'Not specified'}",
                notif_type="request_rejected",
                related_id=req.id,
                related_type="food_request"
            )

        db.session.commit()
        return {"message": f"Request {action}ed", "request": req.to_dict()}, 200

    @staticmethod
    def get_dashboard_analytics(restaurant_id: int) -> dict:
        """Get comprehensive dashboard analytics for restaurant."""
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)

        # Total listings
        total_listings = FoodListing.query.filter_by(restaurant_id=restaurant_id).count()
        active_listings = FoodListing.query.filter_by(restaurant_id=restaurant_id, status="available").count()
        delivered_count = FoodRequest.query.filter_by(restaurant_id=restaurant_id, status="delivered").count()
        pending_requests = FoodRequest.query.filter_by(restaurant_id=restaurant_id, status="pending").count()

        # Food donated this month
        donated_this_month = db.session.query(func.sum(FoodListing.quantity)).filter(
            FoodListing.restaurant_id == restaurant_id,
            FoodListing.status == "delivered",
            FoodListing.updated_at >= thirty_days_ago
        ).scalar() or 0

        # Weekly chart data (last 7 days)
        weekly_data = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            donations = db.session.query(func.count(FoodListing.id)).filter(
                FoodListing.restaurant_id == restaurant_id,
                FoodListing.created_at >= day_start,
                FoodListing.created_at < day_end
            ).scalar() or 0

            history = FoodHistory.query.filter(
                FoodHistory.restaurant_id == restaurant_id,
                FoodHistory.record_date == day.date()
            ).first()

            weekly_data.append({
                "date": day.strftime("%Y-%m-%d"),
                "day": day.strftime("%a"),
                "donations": donations,
                "food_wasted_kg": float(history.food_wasted_kg) if history else 0,
                "food_donated_kg": float(history.food_donated_kg) if history else 0,
                "covers": history.covers_served if history else 0
            })

        # Category breakdown
        category_data = db.session.query(
            FoodListing.category,
            func.count(FoodListing.id).label("count"),
            func.sum(FoodListing.quantity).label("total_kg")
        ).filter(
            FoodListing.restaurant_id == restaurant_id
        ).group_by(FoodListing.category).all()

        categories = [{"category": c.category, "count": c.count, "total_kg": float(c.total_kg or 0)} for c in category_data]

        # Recent activity
        recent_listings = FoodListing.query.filter_by(
            restaurant_id=restaurant_id
        ).order_by(desc(FoodListing.created_at)).limit(5).all()

        # Latest prediction
        latest_prediction = WastePrediction.query.filter_by(
            restaurant_id=restaurant_id
        ).order_by(desc(WastePrediction.created_at)).first()

        return {
            "overview": {
                "total_listings": total_listings,
                "active_listings": active_listings,
                "delivered_count": delivered_count,
                "pending_requests": pending_requests,
                "donated_this_month_kg": float(donated_this_month)
            },
            "weekly_chart": weekly_data,
            "category_breakdown": categories,
            "recent_listings": [l.to_dict() for l in recent_listings],
            "latest_prediction": latest_prediction.to_dict() if latest_prediction else None
        }

    @staticmethod
    def add_food_history(restaurant_id: int, data: dict) -> tuple[dict, int]:
        """Add daily food history record for ML training."""
        from app.models import FoodHistory
        try:
            record_date = datetime.strptime(data["record_date"], "%Y-%m-%d").date()

            # Check for existing record
            existing = FoodHistory.query.filter_by(
                restaurant_id=restaurant_id,
                record_date=record_date
            ).first()

            if existing:
                # Update existing
                for field in ["covers_served", "food_prepared_kg", "food_donated_kg", "food_wasted_kg", "revenue", "weather_condition", "temperature_celsius", "is_holiday", "special_event", "notes"]:
                    if field in data:
                        setattr(existing, field, data[field])
                db.session.commit()
                return {"message": "History updated", "record": existing.to_dict()}, 200
            else:
                record = FoodHistory(
                    restaurant_id=restaurant_id,
                    record_date=record_date,
                    day_of_week=record_date.weekday(),
                    is_holiday=bool(data.get("is_holiday", False)),
                    weather_condition=data.get("weather_condition", "clear"),
                    temperature_celsius=data.get("temperature_celsius"),
                    covers_served=int(data.get("covers_served", 0)),
                    food_prepared_kg=float(data.get("food_prepared_kg", 0)),
                    food_donated_kg=float(data.get("food_donated_kg", 0)),
                    food_wasted_kg=float(data.get("food_wasted_kg", 0)),
                    revenue=float(data.get("revenue", 0)),
                    special_event=data.get("special_event"),
                    notes=data.get("notes")
                )
                db.session.add(record)
                db.session.commit()
                return {"message": "History added", "record": record.to_dict()}, 201

        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500
