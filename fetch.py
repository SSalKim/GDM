import requests
from datetime import datetime, timedelta
import os

SAVE_DIR = "forecast_files/"
os.makedirs(SAVE_DIR, exist_ok=True)

# UTC 현재 시각
now_utc = datetime.utcnow()
hours = [0, 6, 12, 18]
cutoff = now_utc - timedelta(days=1)

# 최신 파일 판단 함수
def get_latest_file(now):
    if 3 <= now.hour < 9:
        hour = 0
    elif 9 <= now.hour < 15:
        hour = 6
    elif 15 <= now.hour < 21:
        hour = 12
    else:  # 21~23, 0~2
        hour = 18
    # 전날 파일 고려
    if hour == 18 and now.hour < 3:
        file_date = now.date() - timedelta(days=1)
    else:
        file_date = now.date()
    return hour, file_date

latest_hour, latest_date = get_latest_file(now_utc)

for hour in hours:
    # 파일 날짜 결정 (전날 포함)
    if hour == latest_hour and hour == 18 and now_utc.hour < 3:
        file_dt = datetime(now_utc.year, now_utc.month, now_utc.day, hour) - timedelta(days=1)
    else:
        file_dt = datetime(latest_date.year, latest_date.month, latest_date.day, hour)

    filename = f"FNV3_{file_dt.year}_{file_dt.month:02d}_{file_dt.day:02d}T{file_dt.hour:02d}_00_atcf_a_deck.txt"
    save_path = os.path.join(SAVE_DIR, filename)
    url = f"https://deepmind.google.com/science/weatherlab/download/cyclones/FNV3/ensemble_mean/paired/atcf/{filename}"

    # 24시간 지난 파일은 건너뜀 (최신 파일 제외)
    if file_dt < cutoff and hour != latest_hour and os.path.exists(save_path):
        print(f"과거 파일 건너뜀: {filename}")
        continue

    # 다운로드 주기 결정
    update_interval = 600 if not os.path.exists(save_path) else 3600  # 초 단위: 10분/1시간

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(r.content)
        print(f"다운로드/갱신 완료: {filename} (interval={update_interval}s)")
    except Exception as e:
        print(f"다운로드 실패 ({filename}): {e}")
