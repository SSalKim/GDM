import requests
from datetime import datetime, timedelta
import os

BASE_DIR = "forecast_files"
hours = [0, 6, 12, 18]
now_utc = datetime.utcnow()
cutoff = now_utc - timedelta(days=1)  # datetime으로 유지

# 최신 파일 판단
def get_latest_file(now):
    if 3 <= now.hour < 9:
        hour = 0
    elif 9 <= now.hour < 15:
        hour = 6
    elif 15 <= now.hour < 21:
        hour = 12
    else:
        hour = 18
    # 전날 파일 고려
    file_date = now.date()
    if hour == 18 and now.hour < 3:
        file_date = file_date - timedelta(days=1)
    return hour, file_date

latest_hour, latest_date = get_latest_file(now_utc)

# 파일별 확인 종료 시간 관리
def get_check_range(hour, date):
    start = datetime(date.year, date.month, date.day, (hour + 6) % 24) - timedelta(hours=3)
    end = start + timedelta(hours=6)
    return start, end

file_check_times = {}
for h in hours:
    start, end = get_check_range(h, latest_date)
    file_check_times[h] = {'start': start, 'end': end}

# 파일 처리
for hour in hours:
    # 항상 datetime 객체 생성 (날짜 + 시간)
    file_dt = datetime.combine(latest_date, datetime.min.time()).replace(hour=hour)

    folder_name = f"{file_dt.year}_{file_dt.month:02d}_{file_dt.day:02d}"
    save_dir = os.path.join(BASE_DIR, folder_name)
    os.makedirs(save_dir, exist_ok=True)

    filename = f"FNV3_{file_dt.year}_{file_dt.month:02d}_{file_dt.day:02d}T{file_dt.hour:02d}_00_atcf_a_deck.txt"
    save_path = os.path.join(save_dir, filename)
    url = f"https://deepmind.google.com/science/weatherlab/download/cyclones/FNV3/ensemble_mean/paired/atcf/{filename}"

    # 과거 파일 처리
    if file_dt < cutoff and hour != latest_hour and os.path.exists(save_path):
        print(f"과거 파일 건너뜀: {filename}")
        continue

    # 다운로드 주기 결정
    update_interval = 600 if not os.path.exists(save_path) else 3600  # 10분/1시간

    # 다운로드 시도
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(r.content)
        print(f"다운로드/갱신 완료: {filename} (interval={update_interval}s)")
    except Exception as e:
        print(f"다운로드 실패 ({filename}): {e}")

    # 확인 종료 시간 체크 및 3시간 연장
    if not os.path.exists(save_path) and now_utc >= file_check_times[hour]['end']:
        file_check_times[hour]['end'] += timedelta(hours=3)
        print(f"{filename} 없음 → 확인 종료 시간 3시간 연장: {file_check_times[hour]['end']}")
