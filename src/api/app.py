"""
Flask entry point for the Soil Sustainability Score API.

Run with:  python src/api/app.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, request, render_template, send_from_directory
from scoring.sss_calculator import SoilSample, calculate_sss
import joblib
import pandas as pd

REPO_ROOT_FOR_APP = Path(__file__).resolve().parent.parent.parent
app = Flask(
    __name__,
    template_folder=str(REPO_ROOT_FOR_APP / "templates"),
    static_folder=str(REPO_ROOT_FOR_APP / "static"),
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = REPO_ROOT / "src" / "models" / "saved"
SCORED_DATA_PATH = REPO_ROOT / "data" / "processed" / "akola_soil_scored.csv"

FEATURE_COLUMNS = [
    "ph", "ec", "organic_carbon", "nitrogen",
    "phosphorus", "potassium", "texture_score",
]
REQUIRED_FIELDS = FEATURE_COLUMNS

try:
    rf_model = joblib.load(MODEL_DIR / "random_forest_model.pkl")
    xgb_model = joblib.load(MODEL_DIR / "xgboost_model.pkl")
    label_encoder = joblib.load(MODEL_DIR / "label_encoder.pkl")
    MODELS_LOADED = True
except FileNotFoundError:
    rf_model = xgb_model = label_encoder = None
    MODELS_LOADED = False

try:
    SCORED_DATA = pd.read_csv(SCORED_DATA_PATH)
    DATA_LOADED = True
except FileNotFoundError:
    SCORED_DATA = None
    DATA_LOADED = False


def parse_soil_input(data):
    if data is None:
        return None, (jsonify({"error": "Request body must be valid JSON"}), 400)

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        return None, (jsonify({
            "error": f"Missing required field(s): {', '.join(missing)}"
        }), 400)

    try:
        values = {field: float(data[field]) for field in REQUIRED_FIELDS}
    except (TypeError, ValueError):
        return None, (jsonify({
            "error": "All soil parameters must be numeric values"
        }), 400)

    return values, None


@app.route("/", methods=["GET"])
def dashboard():
    return render_template("index.html")


@app.route("/map", methods=["GET"])
def view_map():
    map_dir = REPO_ROOT_FOR_APP / "outputs" / "reports"
    map_file = "soil_sustainability_map.html"
    if not (map_dir / map_file).exists():
        return (
            "Map not found. Run src/gis/geocode_villages.py and then "
            "src/gis/generate_map.py first to generate it.",
            404,
        )
    return send_from_directory(map_dir, map_file)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


@app.route("/score", methods=["POST"])
def score_soil():
    data = request.get_json(silent=True)
    values, error = parse_soil_input(data)
    if error:
        return error

    sample = SoilSample(**values)
    result = calculate_sss(sample)
    return jsonify(result), 200


@app.route("/predict", methods=["POST"])
def predict_soil():
    if not MODELS_LOADED:
        return jsonify({
            "error": "ML models not found. Run src/models/train_models.py "
                     "first to generate src/models/saved/*.pkl"
        }), 503

    data = request.get_json(silent=True)
    values, error = parse_soil_input(data)
    if error:
        return error

    sample = SoilSample(**values)
    rule_based_result = calculate_sss(sample)

    features_df = pd.DataFrame([[values[col] for col in FEATURE_COLUMNS]],
                                columns=FEATURE_COLUMNS)

    rf_pred_encoded = rf_model.predict(features_df)[0]
    xgb_pred_encoded = xgb_model.predict(features_df)[0]

    rf_pred_label = label_encoder.inverse_transform([rf_pred_encoded])[0]
    xgb_pred_label = label_encoder.inverse_transform([xgb_pred_encoded])[0]

    return jsonify({
        "rule_based": rule_based_result,
        "random_forest_prediction": rf_pred_label,
        "xgboost_prediction": xgb_pred_label,
    }), 200


@app.route("/score-by-location", methods=["POST"])
def score_by_location():
    """
    Look up soil sustainability scores by location instead of requiring
    raw soil parameters — useful for farmers who don't have lab reports
    on hand but know their village.

    Expected JSON body (at least one field required):
        {
            "state": "Maharashtra",
            "district": "Akola",
            "block": "Akola",
            "village": "Kanheri"
        }

    NOTE: this is a LOOKUP against the existing survey dataset, not a
    live prediction — it only returns results for locations that exist
    in data/processed/akola_soil_scored.csv. If multiple soil profiles
    exist for the same location (common — profiles are taken at
    different points), all matches are returned as a list.
    """
    if not DATA_LOADED:
        return jsonify({
            "error": "Scored soil dataset not found. Run "
                     "src/scoring/score_dataset.py first to generate "
                     "data/processed/akola_soil_scored.csv"
        }), 503

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    location_fields = {
        "state": "State",
        "district": "District",
        "block": "Block",
        "village": "Village",
    }
    provided = {}  # maps column_name -> lowercase search value
    provided_original = {}  # maps original request key -> original value, for error messages
    for key, col in location_fields.items():
        if key in data and str(data[key]).strip() != "":
            provided[col] = str(data[key]).strip().lower()
            provided_original[key] = data[key]

    if not provided:
        return jsonify({
            "error": "Provide at least one location field: "
                     "state, district, block, or village"
        }), 400

    filtered = SCORED_DATA.copy()
    for col, value in provided.items():
        filtered = filtered[filtered[col].astype(str).str.strip().str.lower() == value]

    if filtered.empty:
        return jsonify({
            "error": "No soil profiles found matching that location in "
                     "the current dataset",
            "searched_for": provided_original
        }), 404

    results = filtered.to_dict(orient="records")
    return jsonify({
        "match_count": len(results),
        "profiles": results,
    }), 200


if __name__ == "__main__":
    app.run(debug=True)