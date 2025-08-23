import requests
from datetime import datetime, timedelta
import os

SAVE_DIR = "forecast_files/"
os.makedirs(SAVE_DIR, exist_ok=True)

now_utc = datetime.utcnow()
hours = [0, 6, 12, 18]            # 6시간 간격
cutoff = now_utc - timedelta(days=1)   # 24시간 지난 파일은 건너뜀

# 최신 파일 결정 로직
if now_utc.hour < 9:
    latest_hour = 0
elif now_utc.hour < 15:
    latest_hour = 6
elif now_utc.hour < 21:
    latest_hour = 12
else:
    latest_hour = 18

for hour in hours:
    file_dt = datetime(now_utc.year, now_utc.month, now_utc.day, hour)
    filename = f"FNV3_{file_dt.year}_{file_dt.month:02d}_{file_dt.day:02d}T{file_dt.hour:02d}_00_atcf_a_deck.txt"
    save_path = os.path.join(SAVE_DIR, filename)
    url = f"https://deepmind.google.com/science/weatherlab/download/cyclones/FNV3/ensemble_mean/paired/atcf/{filename}"

    # 과거 파일 처리: 24시간 지난 파일은 이미 있으면 건너뛰기
    if file_dt < cutoff and hour != latest_hour and os.path.exists(save_path):
        print(f"과거 파일 건너뜀: {filename}")
        continue

    # 최신 파일 다운로드/갱신
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(r.content)
        print(f"다운로드 완료/갱신: {filename}")
    except Exception as e:
        print(f"다운로드 실패 ({filename}): {e}")
