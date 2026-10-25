import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

CITY = "Miami, Florida"
LATITUDE = 25.7617
LONGITUDE = -80.1918

TIMEZONE_NAME = "America/New_York"
TIMEZONE = ZoneInfo(TIMEZONE_NAME)

API_URL = "https://api.open-meteo.com/v1/forecast"

TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"


# ---------------------------------------------------------
# GET WEATHER FORECAST
# ---------------------------------------------------------

def get_forecast():

    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": "precipitation_probability",
        "forecast_days": 2,
        "timezone": TIMEZONE_NAME,
    }

    # Retry automatically if the weather server briefly disconnects
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )

    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))

    response = session.get(
        API_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json(), response.url


# ---------------------------------------------------------
# FORMAT DATA FOR ONE FORECAST DATE
# ---------------------------------------------------------

def make_rows(data, target_date, collected_at, request_url):

    times = data["hourly"]["time"]
    probabilities = data["hourly"]["precipitation_probability"]

    rows = []

    for timestamp, probability in zip(times, probabilities):

        forecast_time = datetime.fromisoformat(timestamp)

        if forecast_time.date() == target_date:

            rows.append(
                {
                    "collection_date": collected_at.date().isoformat(),
                    "collection_time_local": collected_at.strftime("%H:%M:%S"),
                    "forecast_date": forecast_time.date().isoformat(),
                    "forecast_hour": forecast_time.strftime("%H:%M"),
                    "precipitation_probability_percent": probability,
                    "city": CITY,
                    "latitude": LATITUDE,
                    "longitude": LONGITUDE,
                    "source": "Open-Meteo Forecast API",
                    "request_url": request_url,
                }
            )

    return rows


# ---------------------------------------------------------
# APPEND ROWS WITHOUT DUPLICATING A DAY
# ---------------------------------------------------------

def append_csv(filename, rows):

    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "collection_date",
        "collection_time_local",
        "forecast_date",
        "forecast_hour",
        "precipitation_probability_percent",
        "city",
        "latitude",
        "longitude",
        "source",
        "request_url",
    ]

    existing_keys = set()

    if path.exists():
        with path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                existing_keys.add(
                    (
                        row["collection_date"],
                        row["forecast_date"],
                        row["forecast_hour"],
                    )
                )

    new_rows = []

    for row in rows:

        key = (
            row["collection_date"],
            row["forecast_date"],
            row["forecast_hour"],
        )

        if key not in existing_keys:
            new_rows.append(row)

    if not new_rows:
        print(f"No new rows needed for {filename}")
        return

    write_header = not path.exists()

    with path.open("a", newline="", encoding="utf-8") as file:

        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if write_header:
            writer.writeheader()

        writer.writerows(new_rows)

    print(f"Saved {len(new_rows)} rows to {filename}")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    now = datetime.now(TIMEZONE)

    print(f"Current Miami time: {now.isoformat()}")

    # Official scheduled collections must occur between 7:30 and 8:30 AM
    start_window = now.replace(
        hour=7,
        minute=30,
        second=0,
        microsecond=0,
    )

    end_window = now.replace(
        hour=8,
        minute=30,
        second=0,
        microsecond=0,
    )

    if not TEST_MODE and not (start_window <= now <= end_window):
        raise RuntimeError(
            f"Collection attempted outside the required window. "
            f"Current Miami time is {now.strftime('%H:%M:%S')}."
        )

    data, request_url = get_forecast()

    today = now.date()
    tomorrow = today + timedelta(days=1)

    same_day_rows = make_rows(
        data,
        today,
        now,
        request_url,
    )

    next_day_rows = make_rows(
        data,
        tomorrow,
        now,
        request_url,
    )

    # Manual GitHub runs are TESTS ONLY.
    # They do not contaminate the official dataset.
    if TEST_MODE:

        print("\n*** TEST MODE — NO DATA WILL BE SAVED ***\n")

        print("Same-day forecast sample:")
        for row in same_day_rows[:3]:
            print(row)

        print("\nNext-day forecast sample:")
        for row in next_day_rows[:3]:
            print(row)

        print("\nTest successful.")

        return

    # Save the two spreadsheets requested by the assignment
    append_csv(
        "data/miami_same_day_forecast.csv",
        same_day_rows,
    )

    append_csv(
        "data/miami_next_day_forecast.csv",
        next_day_rows,
    )

    # Save the untouched API response for data-integrity verification
    raw_directory = Path("data/raw")
    raw_directory.mkdir(parents=True, exist_ok=True)

    raw_filename = (
        raw_directory
        / f"{now.strftime('%Y-%m-%d_%H%M%S')}_forecast.json"
    )

    with raw_filename.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "collected_at_local": now.isoformat(),
                "request_url": request_url,
                "response": data,
            },
            file,
            indent=2,
        )

    print(f"Raw API response saved to {raw_filename}")
    print("\nWeather collection completed successfully.")


if __name__ == "__main__":
    main()
