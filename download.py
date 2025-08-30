import os
import requests
from datetime import datetime, timedelta

# 기본 설정
BASE_DIR = "downloads"
models = ["FNV3", "GENC"]
hours = [18, 12, 6, 0]

# 시작/끝 날짜
start_date = datetime(2025, 6, 1)
end_date   = datetime(2025, 9, 1)

# 날짜 반복
date = start_date
while date <= end_date:
    # 저장 폴더 (예: 2025_06_01)
    folder_name = f"{date.year}_{date.month:02d}_{date.day:02d}"
    save_dir = os.path.join(BASE_DIR, folder_name)
    os.makedirs(save_dir, exist_ok=True)

    for model in models:       
        for hour in hours:     
            # 파일명 및 URL
            filename = f"{model}_{date.year}_{date.month:02d}_{date.day:02d}T{hour:02d}_00_atcf_a_deck.txt"
            save_path = os.path.join(save_dir, filename)
            url = f"https://deepmind.google.com/science/weatherlab/download/cyclones/{model}/ensemble_mean/paired/atcf/{filename}"

            # 다운로드
            try:
                r = requests.get(url, timeout=30)
                if r.status_code == 200:
                    with open(save_path, "wb") as f:
                        f.write(r.content)
                    print(f"✅ Downloaded: {filename}")
                else:
                    print(f"⚠️ {filename} not found (status {r.status_code})")
            except Exception as e:
                print(f"❌ Error downloading {filename}: {e}")

    # 다음 날짜로 이동
    date += timedelta(days=1)
