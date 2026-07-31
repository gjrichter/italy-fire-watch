#!/usr/bin/env python3
"""Fetch recent VIIRS/MODIS hotspots and append new ones to hotspot_history.csv.

Uses NASA FIRMS' public static regional CSV exports (no API key, no rate limit) —
the same source already used by the "iXMapsBot" pipeline in github.com/gjrichter/data
(.github/workflows/update_effis.yml). These are rolling 7-day windows for Europe;
we filter down to Italy client-side since the files don't support server-side filtering.
"""
import argparse
import csv
import datetime
import io
import os
import urllib.request

SOURCES = {
    "viirs_snpp": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Europe_7d.csv",
    "viirs_noaa20": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_7d.csv",
    "modis": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Europe_7d.csv",
}

# Italy bounding box (mainland + Sicily + Sardinia), generous margin.
ITALY_BBOX = {"lat_min": 35.0, "lat_max": 47.5, "lon_min": 6.0, "lon_max": 19.0}

HISTORY_FIELDS = ["id", "source", "satellite", "acq_at", "lat", "lon", "frp", "confidence"]


def fetch_source(name, url):
    with urllib.request.urlopen(url, timeout=60) as resp:
        body = resp.read().decode("utf-8", errors="replace")

    rows = []
    for rec in csv.DictReader(io.StringIO(body)):
        try:
            lat = float(rec["latitude"])
            lon = float(rec["longitude"])
        except (KeyError, ValueError):
            continue
        if not (ITALY_BBOX["lat_min"] <= lat <= ITALY_BBOX["lat_max"] and
                ITALY_BBOX["lon_min"] <= lon <= ITALY_BBOX["lon_max"]):
            continue
        acq_at = f"{rec['acq_date']} {rec['acq_time'][:2]}:{rec['acq_time'][2:]}:00"
        row_id = f"{name}_{rec['acq_date']}_{rec['acq_time']}_{lat:.5f}_{lon:.5f}"
        rows.append({
            "id": row_id,
            "source": name,
            "satellite": rec.get("satellite", ""),
            "acq_at": acq_at,
            "lat": lat,
            "lon": lon,
            "frp": rec.get("frp", ""),
            "confidence": rec.get("confidence", ""),
        })
    return rows


def load_existing_ids(history_path):
    if not os.path.exists(history_path):
        return set()
    with open(history_path, newline="") as f:
        return {row["id"] for row in csv.DictReader(f)}


def append_rows(history_path, rows):
    file_exists = os.path.exists(history_path)
    with open(history_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default=os.path.join(os.path.dirname(__file__), "..", "hotspot_history.csv"))
    args = parser.parse_args()

    history_path = os.path.abspath(args.history)
    existing_ids = load_existing_ids(history_path)

    new_rows = []
    for name, url in SOURCES.items():
        rows = fetch_source(name, url)
        found_new = 0
        for row in rows:
            if row["id"] not in existing_ids:
                new_rows.append(row)
                existing_ids.add(row["id"])
                found_new += 1
        print(f"{name}: {len(rows)} in Italy bbox, {found_new} new")

    append_rows(history_path, new_rows)
    print(f"Fetched {len(new_rows)} new hotspots total, history now has {len(existing_ids)}")


if __name__ == "__main__":
    main()
