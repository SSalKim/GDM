import requests
from datetime import datetime, timedelta
import os

SAVE_DIR = "forecast_files/"
os.makedirs(SAVE_DIR, exist_ok=True)

now = datetime.utcnow()

hours = [0, 6, 12, 18]

cutoff = now - timedelta(days=1)

for hour in hours:
    file_dt = datetime(now.year, now.month, now.day, hour)
    filename = f"FNV3_{file_dt.year}_{file_dt.month:02d}_{file_dt.day:02d}T{file_dt.hour:02d}_00_atcf_a_deck.txt"
    save_path = os.path.join(SAVE_DIR, filename)
    url = f"https://deepmind.google.com/science/weatherlab/download/cyclones/FNV3/ensemble_mean/paired/atcf/{filename}"

    if file_dt < cutoff and os.path.exists(save_path):
        print(f"Skipping Download: {filename}")
        continue

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(r.content)
        print(f"Download success, Data updated: {filename}")
    except Exception as e:
        print(f"Download Failed ({filename}): {e}")
