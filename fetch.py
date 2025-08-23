import requests
from datetime import datetime, timedelta
import os

BASE_DIR = "forecast_files"
now_utc = datetime.utcnow()

# 확인 시간대 (최신 가능성 순)
hours = [18, 12, 6, 0]

# 확인 날짜: 오늘, 전날
dates_to_check = [now_utc.date(), (now_utc - timedelta(days=1)).date()]

# 확인 순서대로 표시
checked_files = []

# 최신 파일 확인
for date in dates_to_check:
    for hour in hours:
        folder_name = f"{date.year}_{date.month:02d}_{date.day:02d}"
        save_dir = os.path.join(BASE_DIR, folder_name)
        os.makedirs(save_dir, exist_ok=True)

        filename = f"FNV3_{date.year}_{date.month:02d}_{date.day:02d}T{hour:02d}_00_atcf_a_deck.txt"
        save_path = os.path.join(save_dir, filename)
        url = f"https://deepmind.google.com/science/weatherlab/download/cyclones/FNV3/ensemble_mean/paired/atcf/{filename}"

        # 로그에 순서 기록
        checked_files.append(filename)

        # 다운로드 시도
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(r.content)
            print(f"다운로드/갱신 완료: {filename}")
            # 최신 파일 찾으면 루프 종료
            break
        except requests.HTTPError as e:
            print(f"다운로드 실패 ({filename}): {e}")
    else:
        # 현재 날짜에 모든 시간 확인했는데 없으면 계속
        continue
    break  # 최신 파일 다운로드 후 전체 종료

# 확인 순서 출력
print("\n확인 순서:")
for f in checked_files:
    print(f)
