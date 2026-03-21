"""
FoodWise AI - Machine Learning: Food Waste Prediction Model
Uses Random Forest + Gradient Boosting ensemble for accurate predictions
"""
import os
import json
import numpy as np
import pandas as pd
import joblib
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
from sklearn.pipeline import Pipeline


class WastePredictor:
    """
    Food Waste Prediction Model
    Features: day_of_week, is_holiday, weather, temperature, covers_served,
              food_prepared_kg, avg_historical_waste, season, month
    Target: food_wasted_kg
    """

    MODEL_VERSION = "1.2.0"

    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.weather_encoder = LabelEncoder()
        self.is_trained = False
        self.feature_names = [
            "day_of_week", "is_holiday", "weather_encoded",
            "temperature_celsius", "covers_served", "food_prepared_kg",
            "month", "is_weekend", "rolling_avg_waste_7d", "waste_ratio_prev"
        ]
        self._init_model()

    def _init_model(self):
        """Initialize ensemble model."""
        self.model = GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=5,
            min_samples_split=5,
            min_samples_leaf=3,
            subsample=0.8,
            random_state=42
        )

    def _encode_weather(self, weather: str) -> int:
        weather_map = {"clear": 0, "cloudy": 1, "rain": 2, "storm": 3, "foggy": 1}
        return weather_map.get(str(weather).lower(), 0)

    def _prepare_features(self, df: pd.DataFrame) -> np.ndarray:
        """Prepare feature matrix from DataFrame."""
        features = pd.DataFrame()

        features["day_of_week"] = df["day_of_week"].astype(int)
        features["is_holiday"] = df["is_holiday"].astype(int)
        features["weather_encoded"] = df["weather_condition"].apply(self._encode_weather)
        features["temperature_celsius"] = df["temperature_celsius"].fillna(30.0).astype(float)
        features["covers_served"] = df["covers_served"].fillna(0).astype(float)
        features["food_prepared_kg"] = df["food_prepared_kg"].fillna(0).astype(float)
        features["month"] = pd.to_datetime(df["record_date"]).dt.month
        features["is_weekend"] = (df["day_of_week"].astype(int) >= 5).astype(int)

        # Rolling avg waste (7-day window if available)
        if "food_wasted_kg" in df.columns:
            features["rolling_avg_waste_7d"] = df["food_wasted_kg"].rolling(7, min_periods=1).mean()
            features["waste_ratio_prev"] = (df["food_wasted_kg"] / df["food_prepared_kg"].replace(0, 1)).shift(1).fillna(0.1)
        else:
            features["rolling_avg_waste_7d"] = features["food_prepared_kg"] * 0.1
            features["waste_ratio_prev"] = 0.1

        return features.values

    def train(self, records: list) -> dict:
        """
        Train the model on historical food data.
        records: list of dicts with keys matching food_history table columns
        """
        if len(records) < 10:
            return {"error": "Need at least 10 historical records to train"}

        df = pd.DataFrame(records)
        df["record_date"] = pd.to_datetime(df["record_date"])
        df = df.sort_values("record_date").reset_index(drop=True)

        X = self._prepare_features(df)
        y = df["food_wasted_kg"].astype(float).values

        # Remove zero-waste rows for better training
        valid_mask = y >= 0
        X, y = X[valid_mask], y[valid_mask]

        if len(X) < 10:
            return {"error": "Insufficient valid training data"}

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train model
        self.model.fit(X_train_scaled, y_train)
        self.is_trained = True

        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)

        # Feature importances
        importances = dict(zip(self.feature_names, self.model.feature_importances_))
        top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "status": "trained",
            "records_used": len(X),
            "metrics": {
                "mae_kg": round(mae, 3),
                "rmse_kg": round(rmse, 3),
                "r2_score": round(r2, 4)
            },
            "top_features": [{"feature": k, "importance": round(v, 4)} for k, v in top_features],
            "model_version": self.MODEL_VERSION
        }

    def predict(self, input_data: dict, history: list = None) -> dict:
        """
        Predict food waste for a given day.
        input_data: {day_of_week, is_holiday, weather_condition, temperature_celsius,
                     covers_served, food_prepared_kg, record_date}
        """
        if not self.is_trained:
            return self._heuristic_prediction(input_data)

        df_row = pd.DataFrame([{
            "day_of_week": input_data.get("day_of_week", datetime.now().weekday()),
            "is_holiday": int(input_data.get("is_holiday", False)),
            "weather_condition": input_data.get("weather_condition", "clear"),
            "temperature_celsius": float(input_data.get("temperature_celsius", 30)),
            "covers_served": float(input_data.get("covers_served", 0)),
            "food_prepared_kg": float(input_data.get("food_prepared_kg", 0)),
            "record_date": input_data.get("record_date", datetime.now().strftime("%Y-%m-%d")),
            "food_wasted_kg": 0
        }])

        X = self._prepare_features(df_row)
        X_scaled = self.scaler.transform(X)
        predicted = max(0, self.model.predict(X_scaled)[0])

        food_prepared = float(input_data.get("food_prepared_kg", 1))
        waste_pct = (predicted / food_prepared * 100) if food_prepared > 0 else 0

        suggestions = self._generate_suggestions(predicted, waste_pct, input_data)

        return {
            "predicted_waste_kg": round(predicted, 2),
            "waste_percentage": round(waste_pct, 1),
            "confidence_level": "high" if self.is_trained else "low",
            "factors": self._explain_prediction(input_data),
            "suggestions": suggestions,
            "model_version": self.MODEL_VERSION
        }

    def _heuristic_prediction(self, input_data: dict) -> dict:
        """Fallback heuristic prediction when model is not trained."""
        food_prepared = float(input_data.get("food_prepared_kg", 0))
        day_of_week = int(input_data.get("day_of_week", 0))
        weather = str(input_data.get("weather_condition", "clear")).lower()
        is_holiday = bool(input_data.get("is_holiday", False))

        base_waste_ratio = 0.12  # 12% baseline waste

        # Adjustments
        if day_of_week in [5, 6]:  # Weekend
            base_waste_ratio -= 0.02
        if weather in ["rain", "storm"]:
            base_waste_ratio += 0.05
        if is_holiday:
            base_waste_ratio -= 0.03

        predicted = food_prepared * base_waste_ratio
        waste_pct = base_waste_ratio * 100

        return {
            "predicted_waste_kg": round(predicted, 2),
            "waste_percentage": round(waste_pct, 1),
            "confidence_level": "low",
            "factors": self._explain_prediction(input_data),
            "suggestions": self._generate_suggestions(predicted, waste_pct, input_data),
            "model_version": self.MODEL_VERSION,
            "note": "Heuristic prediction (insufficient training data)"
        }

    def _explain_prediction(self, input_data: dict) -> list:
        """Generate explanation for the prediction."""
        factors = []
        day = int(input_data.get("day_of_week", 0))
        weather = str(input_data.get("weather_condition", "clear")).lower()
        covers = int(input_data.get("covers_served", 0))
        prepared = float(input_data.get("food_prepared_kg", 0))

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        factors.append({
            "factor": "Day of Week",
            "value": day_names[day] if day < 7 else "Unknown",
            "impact": "positive" if day in [5, 6] else "neutral"
        })

        if weather in ["rain", "storm"]:
            factors.append({"factor": "Weather", "value": weather.capitalize(), "impact": "negative"})
        elif weather == "clear":
            factors.append({"factor": "Weather", "value": "Clear", "impact": "positive"})

        if covers > 0 and prepared > 0:
            ratio = covers / (prepared * 2)  # rough estimate
            if ratio < 0.7:
                factors.append({"factor": "Covers vs Preparation", "value": f"{covers} covers / {prepared}kg prepared", "impact": "negative"})
            else:
                factors.append({"factor": "Covers vs Preparation", "value": f"Well matched", "impact": "positive"})

        if bool(input_data.get("is_holiday", False)):
            factors.append({"factor": "Holiday", "value": "Yes", "impact": "positive"})

        return factors

    def _generate_suggestions(self, predicted_kg: float, waste_pct: float, input_data: dict) -> list:
        """Generate actionable suggestions to reduce waste."""
        suggestions = []

        if waste_pct > 20:
            suggestions.append({
                "priority": "high",
                "title": "Reduce Preparation Volume",
                "description": f"Consider reducing food preparation by {int(waste_pct - 10)}% on similar days to minimize waste.",
                "savings_kg": round(predicted_kg * 0.3, 2)
            })

        if str(input_data.get("weather_condition", "")).lower() in ["rain", "storm"]:
            suggestions.append({
                "priority": "high",
                "title": "Adjust for Rainy Day",
                "description": "Rainy weather reduces foot traffic. Prepare 15-20% less on forecasted rain days.",
                "savings_kg": round(predicted_kg * 0.2, 2)
            })

        suggestions.append({
            "priority": "medium",
            "title": "Early Listing on FoodWise",
            "description": "List surplus food 3+ hours before closing to allow NGOs ample pickup time.",
            "savings_kg": round(predicted_kg * 0.5, 2)
        })

        if int(input_data.get("day_of_week", 0)) not in [5, 6]:
            suggestions.append({
                "priority": "medium",
                "title": "Weekday Portion Control",
                "description": "Weekday lunch portions can be reduced by 10% without impacting customer satisfaction.",
                "savings_kg": round(predicted_kg * 0.15, 2)
            })

        suggestions.append({
            "priority": "low",
            "title": "Staff Meal Program",
            "description": "Use predicted surplus as staff meals to reduce waste before it occurs.",
            "savings_kg": round(predicted_kg * 0.2, 2)
        })

        return suggestions

    def save(self, model_path: str, scaler_path: str):
        """Persist model to disk."""
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(self.model, model_path)
        joblib.dump(self.scaler, scaler_path)

    def load(self, model_path: str, scaler_path: str) -> bool:
        """Load model from disk."""
        try:
            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            self.is_trained = True
            return True
        except Exception:
            return False


# Singleton instance
_predictor_instance = None


def get_predictor() -> WastePredictor:
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = WastePredictor()
        # Try loading saved model
        model_path = os.getenv("MODEL_PATH", "app/ml/models/waste_predictor.pkl")
        scaler_path = os.getenv("MODEL_SCALER_PATH", "app/ml/models/scaler.pkl")
        _predictor_instance.load(model_path, scaler_path)
    return _predictor_instance
