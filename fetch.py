import requests
from datetime import datetime, timedelta
import os

BASE_DIR = "forecast_files"
now_utc = datetime.utcnow()

# 확인 시간대 (최신 가능성 순)
hours = [18, 12, 6, 0]

# 확인 날짜: 오늘, 전날
dates_to_check = [now_utc.date(), (now_utc - timedelta(days=1)).date()]

for date in dates_to_check:
    for hour in hours:
        # 날짜별 폴더 생성
        folder_name = f"{date.year}_{date.month:02d}_{date.day:02d}"
        save_dir = os.path.join(BASE_DIR, folder_name)
        os.makedirs(save_dir, exist_ok=True)

        filename = f"FNV3_{date.year}_{date.month:02d}_{date.day:02d}T{hour:02d}_00_atcf_a_deck.txt"
        save_path = os.path.join(save_dir, filename)
        url = f"https://deepmind.google.com/science/weatherlab/download/cyclones/FNV3/ensemble_mean/paired/atcf/{filename}"

        # 다운로드 시도
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(r.content)
            print(f"다운로드/갱신 완료: {filename}")
        except Exception as e:
            print(f"다운로드 실패 ({filename}): {e}")

        # 최신 파일 확인 후 바로 종료
        break  # 이 파일만 확인하고 루프 종료
    if os.path.exists(save_path):
        break  # 해당 날짜에서 최신 파일 찾았으면 종료
