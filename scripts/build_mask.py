#!/usr/bin/env python3
"""Build exclusion_mask.geojson from known_sources_seed.geojson + persistent grid cells
found in hotspot_history.csv.

A grid cell is promoted to the auto-derived mask when it has been detected on at least
MIN_DAYS distinct calendar days within the last WINDOW_DAYS days — mirroring (loosely,
scaled down since we're bootstrapping from scratch rather than years of archive) the
approach NASA FIRMS uses for its own fixed hotspot mask.
"""
import argparse
import csv
import datetime
import json
import os

GRID_DEG = 0.01          # ~1.1km, matches MODIS pixel / VIIRS geolocation tolerance
MIN_DAYS = 10             # distinct detection days required to call a cell "persistent"
WINDOW_DAYS = 60          # rolling window the MIN_DAYS is counted over
AUTO_BUFFER_M = 750       # tighter than seed buffer since this is an observed pixel cluster


def grid_key(lat, lon):
    return (round(lat / GRID_DEG), round(lon / GRID_DEG))


def grid_center(key):
    return (key[0] * GRID_DEG, key[1] * GRID_DEG)


def load_history(history_path):
    if not os.path.exists(history_path):
        return []
    with open(history_path, newline="") as f:
        return list(csv.DictReader(f))


def find_persistent_cells(rows, now):
    window_start = now - datetime.timedelta(days=WINDOW_DAYS)
    cells = {}  # key -> set of dates
    for row in rows:
        try:
            acq = datetime.datetime.strptime(row["acq_at"][:10], "%Y-%m-%d")
        except (ValueError, KeyError):
            continue
        if acq < window_start:
            continue
        key = grid_key(float(row["lat"]), float(row["lon"]))
        cells.setdefault(key, set()).add(acq.date())

    persistent = {}
    for key, dates in cells.items():
        if len(dates) >= MIN_DAYS:
            persistent[key] = {"days_detected": len(dates), "first_seen": min(dates).isoformat(),
                                "last_seen": max(dates).isoformat()}
    return persistent


def build_mask(seed_path, history_path, out_path, now=None):
    now = now or datetime.datetime.utcnow()

    with open(seed_path) as f:
        seed = json.load(f)

    rows = load_history(history_path)
    persistent_cells = find_persistent_cells(rows, now)

    features = []
    for feat in seed["features"]:
        props = dict(feat["properties"])
        props["origin"] = "seed"
        features.append({"type": "Feature", "properties": props, "geometry": feat["geometry"]})

    for key, stats in persistent_cells.items():
        lat, lon = grid_center(key)
        features.append({
            "type": "Feature",
            "properties": {
                "name": f"auto-derived {lat:.3f},{lon:.3f}",
                "kind": "auto_persistent",
                "origin": "auto",
                "buffer_m": AUTO_BUFFER_M,
                **stats,
            },
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        })

    mask = {
        "type": "FeatureCollection",
        "properties": {
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "seed_count": len(seed["features"]),
            "auto_count": len(persistent_cells),
            "params": {"grid_deg": GRID_DEG, "min_days": MIN_DAYS, "window_days": WINDOW_DAYS,
                       "auto_buffer_m": AUTO_BUFFER_M},
        },
        "features": features,
    }
    with open(out_path, "w") as f:
        json.dump(mask, f, indent=2)
    print(f"exclusion mask: {len(seed['features'])} seed + {len(persistent_cells)} auto-derived = {len(features)} total")


def main():
    base = os.path.join(os.path.dirname(__file__), "..")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=os.path.join(base, "known_sources_seed.geojson"))
    parser.add_argument("--history", default=os.path.join(base, "hotspot_history.csv"))
    parser.add_argument("--out", default=os.path.join(base, "exclusion_mask.geojson"))
    args = parser.parse_args()
    build_mask(args.seed, args.history, args.out)


if __name__ == "__main__":
    main()
