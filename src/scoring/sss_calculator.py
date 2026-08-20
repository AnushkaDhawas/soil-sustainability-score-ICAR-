"""
Soil Sustainability Score (SSS) calculation engine.

    SSS = (0.70 * Chemical Health Score) + (0.30 * Physical Health Score)

Categories:
    80-100  Highly Sustainable
    60-79   Moderately Sustainable
    40-59   Needs Improvement
    < 40    Unsustainable

This module has NO ML dependency — it is the ground-truth label generator
used later to train/validate Random Forest and XGBoost models in src/models/.

SCORING APPROACH
-----------------
Each raw parameter (pH, OC, N, P, K, EC) is converted into a 0-100
"sub-index" using a trapezoidal ideal-range function:

    score = 100   if value is within the ideal range
    score falls off linearly to 0 as the value moves further outside
    the ideal range, until it hits a defined min/max bound

The ideal ranges below are standard indicative ranges used in Indian
Soil Health Card reporting for most cereal/general cropping systems.
TODO: calibrate these ranges to your specific crop type, region, or
      any lab-provided reference ranges before using in production.
"""

from dataclasses import dataclass


@dataclass
class SoilSample:
    ph: float
    organic_carbon: float    # OC, %
    nitrogen: float           # N (available), kg/ha
    phosphorus: float         # P (available), kg/ha
    potassium: float          # K (available), kg/ha
    ec: float                  # Electrical Conductivity, dS/m
    texture_score: float       # 0-100, derived from soil texture class (see below)


def _trapezoidal_score(value: float, low_bound: float, low_ideal: float,
                        high_ideal: float, high_bound: float) -> float:
    """
    Generic trapezoidal scoring function.

    
        low_bound   -> score 0
        low_ideal   -> score 100
        high_ideal  -> score 100
        high_bound  -> score 0

    Values outside [low_bound, high_bound] are clamped to 0.
    """
    if value <= low_bound or value >= high_bound:
        return 0.0
    if low_ideal <= value <= high_ideal:
        return 100.0
    if value < low_ideal:
        return 100.0 * (value - low_bound) / (low_ideal - low_bound)
    # value > high_ideal
    return 100.0 * (high_bound - value) / (high_bound - high_ideal)


def ph_score(ph: float) -> float:
    # Ideal: 6.5-7.5 (neutral). Usable range: 4.5-9.5.
    return _trapezoidal_score(ph, low_bound=4.5, low_ideal=6.5,
                               high_ideal=7.5, high_bound=9.5)


def organic_carbon_score(oc: float) -> float:
    # Ideal: >= 0.75% (high). Below 0.5% is low. No real upper penalty.
    if oc >= 0.75:
        return 100.0
    if oc <= 0.2:
        return 0.0
    return 100.0 * (oc - 0.2) / (0.75 - 0.2)


def nitrogen_score(n: float) -> float:
    # Ideal (available N): 280-560 kg/ha (medium-high). Below 140 = very low.
    return _trapezoidal_score(n, low_bound=140, low_ideal=280,
                               high_ideal=560, high_bound=700)


def phosphorus_score(p: float) -> float:
    # Ideal (available P): 23-56 kg/ha (medium-high). Below 10 = very low.
    return _trapezoidal_score(p, low_bound=10, low_ideal=23,
                               high_ideal=56, high_bound=80)


def potassium_score(k: float) -> float:
    # Ideal (available K): 135-336 kg/ha (medium-high). Below 100 = very low.
    return _trapezoidal_score(k, low_bound=100, low_ideal=135,
                               high_ideal=336, high_bound=450)


def ec_score(ec: float) -> float:
    # Ideal: <= 1.0 dS/m (non-saline, safe for most crops).
    # 1.0-2.0 = slightly saline, penalized. > 4.0 = severely saline (0).
    if ec <= 1.0:
        return 100.0
    if ec >= 4.0:
        return 0.0
    return 100.0 * (4.0 - ec) / (4.0 - 1.0)


def chemical_health_score(sample: SoilSample) -> float:
    """
    Weighted average of the six chemical sub-indices.
    Weights reflect general agronomic importance; adjust as needed.
    """
    weights = {
        "ph": 0.15,
        "oc": 0.25,
        "n": 0.20,
        "p": 0.15,
        "k": 0.15,
        "ec": 0.10,
    }
    scores = {
        "ph": ph_score(sample.ph),
        "oc": organic_carbon_score(sample.organic_carbon),
        "n": nitrogen_score(sample.nitrogen),
        "p": phosphorus_score(sample.phosphorus),
        "k": potassium_score(sample.potassium),
        "ec": ec_score(sample.ec),
    }
    weighted_sum = sum(scores[key] * weights[key] for key in weights)
    return round(weighted_sum, 2)


def physical_health_score(sample: SoilSample) -> float:
    """
    Currently a direct pass-through of the pre-computed texture_score
    (0-100), which should encode soil texture class + water-holding
    capacity. TODO: expand this into its own weighted sub-index once
    you have more physical parameters (bulk density, infiltration
    rate, water-holding capacity) rather than a single derived score.
    """
    return round(max(0.0, min(100.0, sample.texture_score)), 2)


def calculate_sss(sample: SoilSample) -> dict:
    chemical = chemical_health_score(sample)
    physical = physical_health_score(sample)
    score = round(0.70 * chemical + 0.30 * physical, 2)

    if score >= 80:
        category = "Highly Sustainable"
    elif score >= 60:
        category = "Moderately Sustainable"
    elif score >= 40:
        category = "Needs Improvement"
    else:
        category = "Unsustainable"

    return {
        "chemical_health_score": chemical,
        "physical_health_score": physical,
        "sss": score,
        "category": category,
    }


if __name__ == "__main__":
    # Quick manual test — run: python src/scoring/sss_calculator.py
    sample = SoilSample(
        ph=6.8,
        organic_carbon=0.6,
        nitrogen=300,
        phosphorus=30,
        potassium=180,
        ec=0.8,
        texture_score=70,
    )
    result = calculate_sss(sample)
    print(result)
