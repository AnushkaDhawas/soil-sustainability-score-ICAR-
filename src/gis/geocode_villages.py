"""
Geocode soil profile locations (State, District, Block, Village) into
latitude/longitude coordinates using OpenStreetMap's free Nominatim
geocoding service, so they can be plotted on a map.

Run with: python src/gis/geocode_villages.py

NOTE: Nominatim's usage policy requires at most 1 request per second and
a descriptive User-Agent — this script respects both. Geocoding ~86
profiles takes roughly 1-2 minutes since many villages repeat (cached).
Requires internet access.
"""

import time
import pandas as pd
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

SCORED_DATA_PATH = Path("data/processed/akola_soil_scored.csv")
GEOCODED_DATA_PATH = Path("data/processed/akola_soil_scored_geocoded.csv")

geolocator = Nominatim(user_agent="soil-sustainability-score-project")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)


def build_query(row):
    """Build a search string from most specific to least specific location fields."""
    parts = [str(row.get(col, "")).strip() for col in
             ["Village", "Block", "District", "State"]]
    parts = [p for p in parts if p and p.lower() != "nan"]
    return ", ".join(parts) + ", India"


def geocode_unique_locations(df: pd.DataFrame) -> dict:
    """Geocode each unique location once (many profiles share a village)."""
    location_cols = ["State", "District", "Block", "Village"]
    unique_locations = df[location_cols].drop_duplicates()
    print(f"Geocoding {len(unique_locations)} unique locations "
          f"(from {len(df)} total profiles)...")

    cache = {}
    for i, row in unique_locations.iterrows():
        key = tuple(row[col] for col in location_cols)
        query = build_query(row)
        try:
            location = geocode(query)
        except Exception as e:
            print(f"  Warning: geocoding failed for '{query}': {e}")
            location = None

        if location:
            cache[key] = (location.latitude, location.longitude)
            print(f"  Found: {query} -> ({location.latitude:.4f}, {location.longitude:.4f})")
        else:
            cache[key] = (None, None)
            print(f"  Not found: {query}")

    return cache


def main():
    df = pd.read_csv(SCORED_DATA_PATH)
    print(f"Loaded {len(df)} scored soil profiles")

    location_cols = ["State", "District", "Block", "Village"]
    cache = geocode_unique_locations(df)

    df["latitude"] = df.apply(
        lambda row: cache[tuple(row[col] for col in location_cols)][0], axis=1
    )
    df["longitude"] = df.apply(
        lambda row: cache[tuple(row[col] for col in location_cols)][1], axis=1
    )

    found = df["latitude"].notna().sum()
    print(f"\nSuccessfully geocoded {found} of {len(df)} profiles")
    if found < len(df):
        print(f"({len(df) - found} profiles could not be geocoded and will be "
              f"excluded from the map)")

    GEOCODED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(GEOCODED_DATA_PATH, index=False)
    print(f"Saved to {GEOCODED_DATA_PATH}")


if __name__ == "__main__":
    main()