"""
Generate an interactive HTML map showing soil sustainability scores by
location, using the geocoded dataset from geocode_villages.py.

Features:
- Street map + two satellite imagery options (Esri, Google), toggleable
- Higher max zoom so you can zoom into individual fields
- Every profile marker shows its own sequential number
- At high zoom, clustering is disabled entirely so every single profile
  is visible and clickable — none stay hidden inside a cluster

Run with: python src/gis/generate_map.py

Output: outputs/reports/soil_sustainability_map.html
Open this file in any web browser to view/interact with the map.
"""

import pandas as pd
import numpy as np
import folium
from folium.plugins import MarkerCluster
from pathlib import Path

GEOCODED_DATA_PATH = Path("data/processed/akola_soil_scored_geocoded.csv")
MAP_OUTPUT_PATH = Path("outputs/reports/soil_sustainability_map.html")

CATEGORY_COLORS = {
    "Highly Sustainable": "#2E7D32",
    "Moderately Sustainable": "#1565C0",
    "Needs Improvement": "#E67E22",
    "Unsustainable": "#C0392B",
}

MAX_ZOOM = 21  # matches Google satellite's native zoom range


def add_jitter(df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """
    Multiple soil profiles often share the exact same village coordinates.
    Without a small offset, their markers sit perfectly on top of one
    another. This adds a tiny random offset (~30-80 meters) to duplicate
    coordinates so every profile gets its own visible, clickable marker
    even at high zoom.
    """
    rng = np.random.default_rng(seed)
    df = df.copy()

    dup_groups = df.groupby(["latitude", "longitude"])
    for (lat, lon), group in dup_groups:
        if len(group) <= 1:
            continue
        jitter_lat = rng.uniform(-0.0007, 0.0007, size=len(group))
        jitter_lon = rng.uniform(-0.0007, 0.0007, size=len(group))
        df.loc[group.index, "latitude"] = lat + jitter_lat
        df.loc[group.index, "longitude"] = lon + jitter_lon

    return df


def build_popup_html(row, number) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; font-size: 13px; min-width: 200px;">
        <b>Profile #{number} \u2014 {row.get('Village', 'Unknown')}</b><br>
        {row.get('Block', '')}, {row.get('District', '')}, {row.get('State', '')}<br>
        <hr style="margin:4px 0;">
        <b>SSS Score:</b> {row['sss']}<br>
        <b>Category:</b> {row['category']}<br>
        <b>Chemical Health:</b> {row['chemical_health_score']}<br>
        <b>Physical Health:</b> {row['physical_health_score']}<br>
        <hr style="margin:4px 0;">
        pH: {row.get('ph', '-')} | EC: {row.get('ec', '-')}<br>
        OC: {row.get('organic_carbon', '-')} | N: {row.get('nitrogen', '-')}<br>
        P: {row.get('phosphorus', '-')} | K: {row.get('potassium', '-')}
    </div>
    """


def numbered_icon(number: int, color: str) -> folium.DivIcon:
    """A small colored circular marker with the profile's sequential
    number inside it, instead of a generic pin icon."""
    html = f"""
    <div style="
        background-color: {color};
        color: white;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        border: 2px solid white;
        box-shadow: 0 1px 4px rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: Arial, sans-serif;
        font-weight: 700;
        font-size: 12px;
    ">{number}</div>
    """
    return folium.DivIcon(html=html, icon_size=(28, 28), icon_anchor=(14, 14))


def main():
    df = pd.read_csv(GEOCODED_DATA_PATH)
    print(f"Loaded {len(df)} profiles")

    df = df.dropna(subset=["latitude", "longitude"])
    print(f"{len(df)} profiles have valid coordinates and will be mapped")

    if df.empty:
        print("No geocoded profiles found — run src/gis/geocode_villages.py first.")
        return

    df = df.reset_index(drop=True)
    df["profile_number"] = df.index + 1

    df = add_jitter(df)

    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        max_zoom=MAX_ZOOM,
        tiles="OpenStreetMap",
        name="Street Map",
    )
    for layer in m._children.values():
        if isinstance(layer, folium.TileLayer):
            layer.options["maxNativeZoom"] = 19
            layer.options["maxZoom"] = MAX_ZOOM

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
        name="Satellite (Esri)",
        overlay=False,
        control=True,
        max_zoom=MAX_ZOOM,
        max_native_zoom=19,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Map data &copy; Google",
        name="Satellite (Google)",
        overlay=False,
        control=True,
        max_zoom=MAX_ZOOM,
        max_native_zoom=21,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Satellite Labels",
        overlay=True,
        control=True,
        show=False,
        max_zoom=MAX_ZOOM,
        max_native_zoom=19,
    ).add_to(m)

    cluster = MarkerCluster(
        name="Soil Profiles",
        options={
            "disableClusteringAtZoom": 17,
            "maxClusterRadius": 50,
            "spiderfyOnMaxZoom": True,
        },
    ).add_to(m)

    for _, row in df.iterrows():
        color = CATEGORY_COLORS.get(row["category"], "#7f7f7f")
        number = int(row["profile_number"])
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            icon=numbered_icon(number, color),
            popup=folium.Popup(build_popup_html(row, number), max_width=300),
            tooltip=f"#{number} \u2014 {row.get('Village', 'Unknown')} \u2014 {row['category']}",
        ).add_to(cluster)

    folium.LayerControl(collapsed=False).add_to(m)

    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background: white; padding: 12px 16px; border-radius: 6px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-family: Arial, sans-serif; font-size: 13px;">
        <b>Sustainability Category</b><br>
        <span style="color:#2E7D32;">&#9679;</span> Highly Sustainable<br>
        <span style="color:#1565C0;">&#9679;</span> Moderately Sustainable<br>
        <span style="color:#E67E22;">&#9679;</span> Needs Improvement<br>
        <span style="color:#C0392B;">&#9679;</span> Unsustainable<br>
        <hr style="margin:6px 0;">
        <span style="font-size:11px;color:#555;">Numbers = profile ID. Zoom in fully to see every profile individually.</span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    MAP_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(MAP_OUTPUT_PATH))
    print(f"Map saved to {MAP_OUTPUT_PATH}")
    print(f"{len(df)} profiles numbered 1-{len(df)}. Max zoom raised to {MAX_ZOOM}.")
    print("Zoom in past level 17 to see every profile individually (clustering disables automatically).")


if __name__ == "__main__":
    main()