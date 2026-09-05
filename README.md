# GDM: Weather Lab Cyclone Guidance

GenCast, WeatherNext2 Cyclones, WeatherNext3 Cyclones의 ensemble mean / paired
ATCF a-deck를 수집합니다. 본문 모델 코드와 cycle을 검증하고 원본 헤더를 보존합니다.

| 모델 | 본문 ATCF 코드 | 우선 다운로드 버전 |
|---|---|---|
| GenCast | GENC | GENC |
| WeatherNext2 Cyclones | FNV3 | FNV3P2, 없으면 FNV3 |
| WeatherNext3 Cyclones | WNV3 | WNV3 |

## 파일 구조

```text
scripts/collect_weatherlab.py              공통 수집·검증 코드
fetch.py                                 기존 실시간 실행 진입점
download.py                              수동 기간 수집 진입점
forecast_files/2026/09/05/GENC_2026_09_05T00_00_atcf_a_deck.txt
forecast_files/2026/09/05/FNV3_2026_09_05T00_00_atcf_a_deck.txt
forecast_files/2026/09/05/WNV3_2026_09_05T00_00_atcf_a_deck.txt
forecast_files/YYYY/MM/DD/<동일한 파일명>.json  원본 버전·검증 메타데이터
data/latest.json                         모델별 최신 정상 cycle
tests/                                   수집 회귀 테스트
```

JSON에는 원본 URL, upstream 버전, ATCF 코드, cycle, 행 수, SHA-256을 기록합니다.
내용이 같으면 파일을 다시 쓰지 않으며 조회 시각만 바뀌는 불필요한 커밋을 만들지 않습니다.
기존 과거 자료는 내용과 파일명을 그대로 유지하며 YYYY_MM_DD에서 YYYY/MM/DD로 이동합니다.
첫 실행에서도 구 폴더를 자동 정리하며, 대상 파일의 내용이 다르면 덮어쓰지 않고 중단합니다.
CDS는 새 URL을 우선 사용하고 구 URL은 fallback으로만 조회합니다.
별도 소비자가 있다면 forecast_files/YYYY/MM/DD 경로로 변경해야 합니다.

## 자동 실행

Cloudflare 외부 cron이 기존 `.github/workflows/fetch.yml`을 호출하는 구조를 유지합니다.
**GitHub 내부 schedule은 추가하지 않습니다.** 기존 workflow 파일명과 이름도 유지합니다.
최근 48시간의 00/06/12/18UTC cycle을 모두 확인하므로 최신 파일 하나를 찾았다고
이전 cycle이나 다른 모델 확인을 중단하지 않습니다.

두 진입 workflow는 `collect.yml`을 공유하며 같은 브랜치의 수집·push는 동시에 실행하지 않습니다.
checkout/push는 내장 `GITHUB_TOKEN`의 contents:write를 사용합니다.
Cloudflare의 workflow_dispatch 인증 설정은 기존 것을 그대로 사용합니다.

404/410은 아직 자료가 없는 것으로 처리합니다. 429/일시적 서버 오류는 제한적으로 재시도하고,
HTML·빈 응답·다른 cycle·다른 모델·손상 행은 기존 파일에 덮어쓰지 않습니다.
일부 다운로드가 실패해도 다른 정상 모델은 보존·커밋한 뒤 run에 오류를 표시합니다.
같은 cycle에서 FNV3P2로 갱신된 파일을 구 FNV3 응답으로 되돌리지 않습니다.

## 수동 실행

```sh
python -m pip install -r requirements.txt
python fetch.py
python download.py --start 2026090400 --end 2026090418
python fetch.py --models WNV3 --lookback-hours 72
python -m unittest discover -s tests -v
```

Actions의 **Download Cyclone Data**에서도 시작·종료 cycle을 지정할 수 있습니다.
둘 다 비우면 실시간과 동일한 최근 48시간을 수집합니다. 범위는 최대 31일이며
미래 cycle은 허용하지 않습니다. GenCast 등 특정 모델의 공급 중단·미공개 자료를
다른 모델로 대체하지 않습니다.

상위 자료: [Google Weather Lab](https://deepmind.google.com/science/weatherlab/).
원본 파일의 이용조건·출처 헤더를 그대로 유지합니다.
