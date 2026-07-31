#!/usr/bin/env python3
"""Produce italy_fires_current.geojson: recent hotspots from hotspot_history.csv with
anything falling inside the exclusion_mask.geojson buffer removed.
"""
import argparse
import csv
import datetime
import json
import math
import os

EARTH_R_M = 6371000


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(a))


def load_mask_points(mask_path):
    with open(mask_path) as f:
        mask = json.load(f)
    points = []
    for feat in mask["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        buffer_m = feat["properties"].get("buffer_m", 1000)
        points.append((lat, lon, buffer_m))
    return points


def is_excluded(lat, lon, mask_points):
    for m_lat, m_lon, buffer_m in mask_points:
        # cheap pre-filter before the trig-heavy haversine call
        if abs(lat - m_lat) > 0.05 or abs(lon - m_lon) > 0.05:
            continue
        if haversine_m(lat, lon, m_lat, m_lon) <= buffer_m:
            return True
    return False


def load_recent_hotspots(history_path, days):
    if not os.path.exists(history_path):
        return []
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    rows = []
    with open(history_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                acq = datetime.datetime.strptime(row["acq_at"][:19], "%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError):
                continue
            if acq >= cutoff:
                rows.append(row)
    return rows


def build_current(history_path, mask_path, out_path, out_csv_path, out_stats_path, days):
    mask_points = load_mask_points(mask_path)
    rows = load_recent_hotspots(history_path, days)

    kept = []
    excluded_count = 0
    for row in rows:
        lat, lon = float(row["lat"]), float(row["lon"])
        if is_excluded(lat, lon, mask_points):
            excluded_count += 1
            continue
        kept.append(row)

    features = [{
        "type": "Feature",
        "properties": {
            "source": row["source"],
            "satellite": row["satellite"],
            "acq_at": row["acq_at"],
            "frp": row["frp"],
            "confidence": row["confidence"],
        },
        "geometry": {"type": "Point", "coordinates": [float(row["lon"]), float(row["lat"])]},
    } for row in kept]

    out = {
        "type": "FeatureCollection",
        "properties": {
            "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "window_days": days,
            "excluded_count": excluded_count,
        },
        "features": features,
    }
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    with open(out_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["lat", "lon", "frp", "confidence", "satellite", "source", "acq_at"])
        writer.writeheader()
        for row in kept:
            writer.writerow({k: row[k] for k in writer.fieldnames})

    # Small standalone stats file — pages showing header counts should fetch this
    # instead of the full geojson/csv just to read two numbers.
    with open(out_stats_path, "w") as f:
        json.dump({
            "generated_at": out["properties"]["generated_at"],
            "window_days": days,
            "kept": len(features),
            "excluded_count": excluded_count,
        }, f, indent=2)

    print(f"italy_fires_current: {len(features)} hotspots kept, {excluded_count} excluded by mask")


def main():
    base = os.path.join(os.path.dirname(__file__), "..")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default=os.path.join(base, "hotspot_history.csv"))
    parser.add_argument("--mask", default=os.path.join(base, "exclusion_mask.geojson"))
    parser.add_argument("--out", default=os.path.join(base, "italy_fires_current.geojson"))
    parser.add_argument("--out-csv", default=os.path.join(base, "italy_fires_current.csv"))
    parser.add_argument("--out-stats", default=os.path.join(base, "italy_fires_stats.json"))
    parser.add_argument("--days", type=int, default=2, help="How many days of recent hotspots to publish")
    args = parser.parse_args()
    build_current(args.history, args.mask, args.out, args.out_csv, args.out_stats, args.days)


if __name__ == "__main__":
    main()
