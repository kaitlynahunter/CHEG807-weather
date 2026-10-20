import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import os

# -----------------------------
# Miami, Florida
# -----------------------------
CITY = "Miami, FL"
LATITUDE = 25.7617
LONGITUDE = -80.1918
TIMEZONE = "America/New_York"

SOURCE = "Open-Meteo Weather Forecast API"
SOURCE_URL = "https://open-meteo.com/en/docs"

# -----------------------------
# Request forecast
# -----------------------------
url = "https://api.open-meteo.com/v1/forecast"

params = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "hourly": [
        "precipitation_probability",
        "precipitation"
    ],
    "forecast_days": 3,
    "timezone": TIMEZONE
}

response = requests.get(url, params=params)
response.raise_for_status()

data = response.json()

# -----------------------------
# Make dataframe
# -----------------------------
forecast = pd.DataFrame({
    "ForecastTime": data["hourly"]["time"],
    "RainChance_pct": data["hourly"]["precipitation_probability"],
    "PredictedPrecip_mm": data["hourly"]["precipitation"]
})

forecast["ForecastTime"] = pd.to_datetime(forecast["ForecastTime"])

# Time forecast was collected
now = datetime.now(ZoneInfo(TIMEZONE))

forecast["CollectionTime"] = now.strftime("%Y-%m-%d %H:%M")
forecast["City"] = CITY
forecast["Source"] = SOURCE
forecast["Source_URL"] = SOURCE_URL

# -----------------------------
# Keep next 48 hours
# -----------------------------
current_hour = pd.Timestamp(
    now.replace(minute=0, second=0, microsecond=0)
).tz_localize(None)

forecast = forecast[
    (forecast["ForecastTime"] >= current_hour) &
    (forecast["ForecastTime"] < current_hour + pd.Timedelta(hours=48))
].copy()

# Label forecast day
collection_date = pd.Timestamp(now.date())

forecast["DaysAhead"] = (
    forecast["ForecastTime"].dt.normalize()
    - collection_date
).dt.days

forecast["PredictionType"] = forecast["DaysAhead"].map({
    0: "Same Day",
    1: "Next Day",
    2: "Two Days Ahead"
})

# -----------------------------
# Save / append CSV
# -----------------------------
filename = "miami_weather_forecast_log.csv"

if os.path.exists(filename):
    forecast.to_csv(
        filename,
        mode="a",
        header=False,
        index=False
    )
else:
    forecast.to_csv(
        filename,
        index=False
    )

print("Miami weather forecast successfully collected.")
print("Collection time:", now)
print("Rows added:", len(forecast))
