import requests
from datetime import datetime, timedelta
import os

BASE_DIR = "forecast_files"
now_utc = datetime.utcnow()

# 확인 시간대 (최신 가능성 순)
hours = [18, 12, 6, 0]

# 확인 날짜: 오늘, 전날
dates_to_check = [now_utc.date(), (now_utc - timedelta(days=1)).date()]

# 최신 파일 찾기 (역순)
latest_file_found = None
for date in dates_to_check:
    for hour in hours:
        folder_name = f"{date.year}_{date.month:02d}_{date.day:02d}"
        save_dir = os.path.join(BASE_DIR, folder_name)
        os.makedirs(save_dir, exist_ok=True)

        filename = f"FNV3_{date.year}_{date.month:02d}_{date.day:02d}T{hour:02d}_00_atcf_a_deck.txt"
        save_path = os.path.join(save_dir, filename)
        url = f"https://deepmind.google.com/science/weatherlab/download/cyclones/FNV3/ensemble_mean/paired/atcf/{filename}"

        # 파일 존재 여부 확인
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(r.content)
            print(f"다운로드/갱신 완료: {filename}")
        except Exception as e:
            print(f"다운로드 실패 ({filename}): {e}")

        # 최신 파일 찾으면 종료
        latest_file_found = filename
        break
    if latest_file_found:
        break
