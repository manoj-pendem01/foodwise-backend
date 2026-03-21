"""
FoodWise AI - ML Service Layer
"""
import os
from datetime import datetime, timedelta
from app import db
from app.models import FoodHistory, WastePrediction, Restaurant
from app.ml.predictor import get_predictor


class MLService:

    @staticmethod
    def train_for_restaurant(restaurant_id: int) -> dict:
        """Train or retrain the ML model for a restaurant."""
        records = FoodHistory.query.filter_by(
            restaurant_id=restaurant_id
        ).order_by(FoodHistory.record_date).all()

        if len(records) < 10:
            return {
                "success": False,
                "error": f"Need at least 10 historical records. You have {len(records)}."
            }, 400

        data = [r.to_dict() for r in records]
        predictor = get_predictor()
        result = predictor.train(data)

        if "error" in result:
            return {"success": False, "error": result["error"]}, 400

        # Save model
        model_path = os.getenv("MODEL_PATH", "app/ml/models/waste_predictor.pkl")
        scaler_path = os.getenv("MODEL_SCALER_PATH", "app/ml/models/scaler.pkl")
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        predictor.save(model_path, scaler_path)

        return {"success": True, "training_result": result}, 200

    @staticmethod
    def predict_waste(restaurant_id: int, prediction_date: str = None, input_data: dict = None) -> dict:
        """Generate waste prediction for a restaurant."""
        if prediction_date is None:
            prediction_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

        pred_date = datetime.strptime(prediction_date, "%Y-%m-%d").date()

        # Get restaurant's recent history for context
        history = FoodHistory.query.filter_by(
            restaurant_id=restaurant_id
        ).order_by(FoodHistory.record_date.desc()).limit(30).all()

        restaurant = Restaurant.query.get(restaurant_id)
        if not restaurant:
            return {"error": "Restaurant not found"}, 404

        # Build prediction input
        if not input_data:
            input_data = {}

        if not input_data.get("food_prepared_kg"):
            avg_prepared = sum(float(h.food_prepared_kg) for h in history) / len(history) if history else 50.0
            input_data["food_prepared_kg"] = avg_prepared

        if not input_data.get("covers_served"):
            input_data["covers_served"] = restaurant.avg_daily_covers

        input_data.setdefault("day_of_week", pred_date.weekday())
        input_data.setdefault("is_holiday", False)
        input_data.setdefault("weather_condition", "clear")
        input_data.setdefault("temperature_celsius", 30.0)
        input_data["record_date"] = prediction_date

        predictor = get_predictor()

        # Train if needed (auto-train on first prediction)
        if not predictor.is_trained and len(history) >= 10:
            data = [r.to_dict() for r in history]
            predictor.train(data)

        prediction = predictor.predict(input_data, [r.to_dict() for r in history])

        # Store prediction in database
        existing = WastePrediction.query.filter_by(
            restaurant_id=restaurant_id,
            prediction_date=pred_date
        ).first()

        if existing:
            existing.predicted_waste_kg = prediction["predicted_waste_kg"]
            existing.confidence_score = 0.85 if prediction["confidence_level"] == "high" else 0.6
            existing.factors = prediction["factors"]
            existing.suggestions = prediction["suggestions"]
            existing.model_version = prediction["model_version"]
        else:
            wp = WastePrediction(
                restaurant_id=restaurant_id,
                prediction_date=pred_date,
                predicted_waste_kg=prediction["predicted_waste_kg"],
                confidence_score=0.85 if prediction["confidence_level"] == "high" else 0.6,
                factors=prediction["factors"],
                suggestions=prediction["suggestions"],
                model_version=prediction["model_version"]
            )
            db.session.add(wp)

        db.session.commit()

        return {"prediction": prediction, "date": prediction_date}, 200

    @staticmethod
    def get_prediction_history(restaurant_id: int, days: int = 30) -> dict:
        """Get past predictions and actuals for analytics."""
        from sqlalchemy import desc
        predictions = WastePrediction.query.filter_by(
            restaurant_id=restaurant_id
        ).order_by(desc(WastePrediction.prediction_date)).limit(days).all()

        return {
            "predictions": [p.to_dict() for p in predictions],
            "total": len(predictions)
        }

    @staticmethod
    def get_waste_insights(restaurant_id: int) -> dict:
        """Generate comprehensive waste insights for a restaurant."""
        history = FoodHistory.query.filter_by(
            restaurant_id=restaurant_id
        ).order_by(FoodHistory.record_date.desc()).limit(90).all()

        if not history:
            return {"message": "No historical data available"}

        total_prepared = sum(float(h.food_prepared_kg) for h in history)
        total_wasted = sum(float(h.food_wasted_kg) for h in history)
        total_donated = sum(float(h.food_donated_kg) for h in history)
        avg_waste_ratio = (total_wasted / total_prepared * 100) if total_prepared > 0 else 0

        # Best and worst days
        sorted_by_waste = sorted(history, key=lambda h: float(h.food_wasted_kg))
        best_day = sorted_by_waste[0] if sorted_by_waste else None
        worst_day = sorted_by_waste[-1] if sorted_by_waste else None

        # Weather impact analysis
        weather_waste = {}
        for h in history:
            weather = h.weather_condition or "clear"
            if weather not in weather_waste:
                weather_waste[weather] = []
            if float(h.food_prepared_kg) > 0:
                weather_waste[weather].append(float(h.food_wasted_kg) / float(h.food_prepared_kg))

        weather_impact = {
            w: round(sum(v) / len(v) * 100, 1)
            for w, v in weather_waste.items() if v
        }

        # Day of week analysis
        dow_waste = {i: [] for i in range(7)}
        dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for h in history:
            if float(h.food_prepared_kg) > 0:
                dow_waste[h.day_of_week].append(float(h.food_wasted_kg) / float(h.food_prepared_kg))

        day_analysis = [
            {
                "day": dow_names[i],
                "avg_waste_pct": round(sum(v) / len(v) * 100, 1) if v else 0
            }
            for i, v in dow_waste.items()
        ]

        # Monthly trend
        monthly = {}
        for h in history:
            month_key = h.record_date.strftime("%Y-%m") if h.record_date else "unknown"
            if month_key not in monthly:
                monthly[month_key] = {"prepared": 0, "wasted": 0, "donated": 0}
            monthly[month_key]["prepared"] += float(h.food_prepared_kg)
            monthly[month_key]["wasted"] += float(h.food_wasted_kg)
            monthly[month_key]["donated"] += float(h.food_donated_kg)

        monthly_trend = [
            {
                "month": k,
                "prepared_kg": round(v["prepared"], 2),
                "wasted_kg": round(v["wasted"], 2),
                "donated_kg": round(v["donated"], 2),
                "waste_pct": round(v["wasted"] / v["prepared"] * 100, 1) if v["prepared"] > 0 else 0
            }
            for k, v in sorted(monthly.items())
        ]

        return {
            "summary": {
                "total_prepared_kg": round(total_prepared, 2),
                "total_wasted_kg": round(total_wasted, 2),
                "total_donated_kg": round(total_donated, 2),
                "avg_waste_percentage": round(avg_waste_ratio, 1),
                "days_analyzed": len(history)
            },
            "best_day": best_day.to_dict() if best_day else None,
            "worst_day": worst_day.to_dict() if worst_day else None,
            "weather_impact": weather_impact,
            "day_of_week_analysis": day_analysis,
            "monthly_trend": monthly_trend,
            "potential_savings_kg_per_month": round(total_wasted / 3 * 0.4, 2)
        }
