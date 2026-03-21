"""
FoodWise AI - Matching Service
Distance-based and intelligent matching between restaurants and NGOs
"""
from datetime import datetime
from flask import current_app
from app import db
from app.models import FoodListing, NGO, FoodRequest
from app.utils import haversine_distance


class MatchingService:

    @staticmethod
    def calculate_match_score(listing: FoodListing, ngo: NGO, distance_km: float) -> float:
        """
        Calculate a match score (0-100) between a listing and NGO.
        Considers: distance, urgency (time to expiry), quantity, dietary preferences.
        """
        score = 100.0

        # Distance penalty (max 25km range, -2 points per km)
        max_distance = current_app.config.get("MAX_MATCH_DISTANCE_KM", 25)
        distance_score = max(0, 100 - (distance_km / max_distance) * 50)

        # Urgency bonus (less time = higher urgency = higher score)
        time_remaining = (listing.expiry_time - datetime.utcnow()).total_seconds() / 3600
        if time_remaining <= 1:
            urgency_score = 100
        elif time_remaining <= 3:
            urgency_score = 80
        elif time_remaining <= 6:
            urgency_score = 60
        else:
            urgency_score = 40

        # Quantity score
        if float(listing.quantity) >= 10:
            quantity_score = 100
        elif float(listing.quantity) >= 5:
            quantity_score = 70
        else:
            quantity_score = 50

        # Weighted composite score
        score = (distance_score * 0.4) + (urgency_score * 0.4) + (quantity_score * 0.2)
        return round(score, 2)

    @staticmethod
    def find_matching_ngos(listing_id: int) -> list:
        """Find NGOs that match a food listing based on location and criteria."""
        listing = FoodListing.query.get(listing_id)
        if not listing or listing.status != "available":
            return []

        max_distance = current_app.config.get("MAX_MATCH_DISTANCE_KM", 25)
        all_ngos = NGO.query.filter_by(is_verified=True).all()

        matches = []
        for ngo in all_ngos:
            distance = haversine_distance(
                float(listing.restaurant.latitude), float(listing.restaurant.longitude),
                float(ngo.latitude), float(ngo.longitude)
            )

            if distance <= max_distance:
                # Check no existing request
                existing = FoodRequest.query.filter_by(
                    food_listing_id=listing_id,
                    ngo_id=ngo.id
                ).first()

                if not existing:
                    score = MatchingService.calculate_match_score(listing, ngo, distance)
                    matches.append({
                        "ngo": ngo.to_dict(),
                        "distance_km": round(distance, 2),
                        "match_score": score
                    })

        # Sort by match score (highest first)
        matches.sort(key=lambda x: x["match_score"], reverse=True)
        return matches

    @staticmethod
    def match_listing(listing_id: int) -> None:
        """Auto-match a listing with the best NGO if auto-match is enabled."""
        try:
            from app.models import SystemSetting
            # Check auto-match setting from DB if available
        except Exception:
            pass

        matches = MatchingService.find_matching_ngos(listing_id)
        if not matches:
            return

        # Notify top 3 NGOs
        listing = FoodListing.query.get(listing_id)
        if not listing:
            return

        from app.notifications.service import NotificationService
        for match in matches[:3]:
            ngo_id = match["ngo"]["id"]
            ngo = NGO.query.get(ngo_id)
            if ngo:
                NotificationService.send_notification(
                    user_id=ngo.user_id,
                    title=f"Food Available Nearby! 🍱 ({match['distance_km']} km)",
                    message=f"'{listing.title}' - {listing.quantity}{listing.unit} available from {listing.restaurant.name}. Expires in {int((listing.expiry_time - datetime.utcnow()).total_seconds() / 3600)}h.",
                    notif_type="food_available",
                    related_id=listing_id,
                    related_type="food_listing"
                )

    @staticmethod
    def run_auto_matching() -> None:
        """Background task: match all available listings."""
        listings = FoodListing.query.filter(
            FoodListing.status == "available",
            FoodListing.expiry_time > datetime.utcnow()
        ).all()

        for listing in listings:
            try:
                MatchingService.match_listing(listing.id)
            except Exception as e:
                current_app.logger.error(f"Matching error for listing {listing.id}: {e}")

    @staticmethod
    def get_nearby_food_for_ngo(ngo_id: int, max_distance_km: float = 25) -> list:
        """Get all available food within range of an NGO."""
        ngo = NGO.query.get(ngo_id)
        if not ngo:
            return []

        listings = FoodListing.query.filter(
            FoodListing.status == "available",
            FoodListing.expiry_time > datetime.utcnow()
        ).all()

        result = []
        for listing in listings:
            if listing.restaurant:
                distance = haversine_distance(
                    float(ngo.latitude), float(ngo.longitude),
                    float(listing.restaurant.latitude), float(listing.restaurant.longitude)
                )
                if distance <= max_distance_km:
                    score = MatchingService.calculate_match_score(listing, ngo, distance)
                    item = listing.to_dict()
                    item["distance_km"] = round(distance, 2)
                    item["match_score"] = score
                    result.append(item)

        result.sort(key=lambda x: x["match_score"], reverse=True)
        return result
