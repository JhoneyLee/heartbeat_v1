# Garmin Connect Heart Rate Collector

Garmin Connect 앱의 심박수 데이터를 주기적으로 가져와서 로컬에 저장하고 분석하는 작은 프로젝트입니다.

이 저장소는 개인 계정 기준으로 가장 현실적인 방법인 비공식 `python-garminconnect` 라이브러리를 사용합니다. Garmin의 공식 Garmin Connect Developer Program은 현재도 존재하지만 승인된 비즈니스 개발자 대상으로 안내되고 있어, 개인 자동화에는 바로 쓰기 어렵습니다.

## 바로 보기

- GitHub Pages 배포용 엔트리: `docs/index.html`
- GitHub Pages 예상 URL: `https://jhoneylee.github.io/heartbeat_v1/`
- 메인 대시보드: `reports/heart_rate_dashboard.html`
- 대시보드 데이터: `reports/dashboard_data/dashboard_data.js`
- 활동별 고해상도 데이터: `reports/dashboard_data/activities/`

## 포함된 것

- `scripts/fetch_garmin_heart_rate.py`: Garmin Connect에서 날짜별 심박수 데이터를 가져와 raw JSON과 SQLite로 저장
- `scripts/fetch_garmin_heart_rate_fine.py`: 웰니스 심박수와 활동 원본 FIT를 함께 가져와 가능한 가장 촘촘한 심박수 샘플까지 저장
- `scripts/analyze_heart_rate.py`: 저장된 데이터를 CSV, 텍스트 요약, PNG 차트, Chart.js 대시보드로 분석하고 GitHub Pages용 `docs/` 정적 파일도 생성
- `launchd/com.user.garmin-heart-rate-fetch.plist.example`: macOS `launchd` 주기 실행 예시
- `.env.example`: 로컬 환경변수 예시

## 데이터 저장 위치

- Raw JSON: `data/raw/heart_rate/YYYY-MM-DD.json`
- Raw activity files: `data/raw/activities/`
- SQLite: `data/processed/garmin_heart_rate.sqlite3`
- 분석 결과: `reports/`

## 1. 환경 준비

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 Garmin 계정 정보를 넣습니다.

```env
GARMIN_EMAIL=your_email@example.com
GARMIN_PASSWORD=your_password
GARMIN_TOKENS_DIR=~/.garminconnect
GARMIN_TIMEZONE=Asia/Seoul
```

첫 로그인 때 MFA가 켜져 있으면 터미널에서 코드를 물어봅니다. 성공하면 토큰이 `GARMIN_TOKENS_DIR` 아래에 저장되고, 이후에는 자동 갱신을 시도합니다.

## 2. 데이터 수집

오늘 데이터 1일치:

```bash
source .venv/bin/activate
python scripts/fetch_garmin_heart_rate.py
```

가장 촘촘한 심박수까지 함께 수집:

```bash
python scripts/fetch_garmin_heart_rate_fine.py --days 1
```

최근 7일 백필:

```bash
python scripts/fetch_garmin_heart_rate.py --days 7
```

특정 기간 백필:

```bash
python scripts/fetch_garmin_heart_rate.py --start-date 2026-05-01 --end-date 2026-05-05
```

## 3. 분석 실행

```bash
source .venv/bin/activate
python scripts/analyze_heart_rate.py
```

대시보드를 바로 열고 싶으면:

```bash
open reports/heart_rate_dashboard.html
```

생성 결과:

- `docs/index.html`
- `docs/dashboard_data/dashboard_data.js`
- `docs/dashboard_data/activities/`
- `reports/heart_rate_dashboard.html`
- `reports/dashboard_data/dashboard_data.js`
- `reports/dashboard_data/activities/`
- `reports/heart_rate_daily_summary.csv`
- `reports/heart_rate_summary.txt`
- `reports/heart_rate_trend.png`
- `reports/heart_rate_hourly_profile.png`

대시보드 기능:

- 기본 기간: 최근 28일
- 기간 직접 선택 및 `28일 / 90일 / YTD / All` 프리셋
- `Daily / Weekly / Monthly` 추세 전환
- 시간대별 심박수 프로필
- 활동 타입 필터
- 활동별 고해상도 심박수 차트와 스파이크 표시
- `running` 활동 고해상도 심박수의 날짜별 대표 평균/최대 추세

## 4. GitHub Pages 배포

분석 스크립트를 실행하면 `docs/` 아래에 GitHub Pages용 정적 파일이 함께 생성됩니다.

```bash
source .venv/bin/activate
python scripts/analyze_heart_rate.py
```

처음 한 번만 GitHub 저장소 설정에서 아래처럼 맞추면 됩니다.

- `Settings > Pages`
- `Build and deployment`: `Deploy from a branch`
- Branch: `main`
- Folder: `/docs`

설정 후에는 `docs/index.html`이 Pages의 기본 엔트리가 되고, 대시보드는 보통 아래 URL에서 열립니다.

- `https://jhoneylee.github.io/heartbeat_v1/`

## 5. macOS에서 주기 실행

예시 파일 `launchd/com.user.garmin-heart-rate-fetch.plist.example` 안의 `__PROJECT_ROOT__`를 실제 프로젝트 경로로 바꾸고, 계정 정보도 수정합니다.

예시 경로:

`/Users/jhoneylee/Documents/New project 2`

그다음 아래처럼 등록합니다.

```bash
cp launchd/com.user.garmin-heart-rate-fetch.plist.example ~/Library/LaunchAgents/com.user.garmin-heart-rate-fetch.plist
launchctl unload ~/Library/LaunchAgents/com.user.garmin-heart-rate-fetch.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.user.garmin-heart-rate-fetch.plist
launchctl start com.user.garmin-heart-rate-fetch
```

기본 설정은 `3600`초마다 1회 실행입니다.

## 참고 사항

- Garmin Connect 쪽 인증 플로우는 바뀔 수 있어서, 비공식 라이브러리 업데이트가 필요할 수 있습니다.
- Garmin 지원 문서 기준으로 Garmin Connect의 하루 심박수 값은 워치의 15초 평균과 달리 2분 평균으로 보일 수 있습니다.
- 더 촘촘한 심박수는 하루 웰니스 그래프가 아니라 활동 원본 `FIT` 파일에서 가져오는 것이 핵심입니다. 활동 중에는 기기와 활동 종류에 따라 1초 수준 또는 그에 가까운 간격으로 기록될 수 있지만, 하루 전체 웰니스 데이터는 그 해상도로 노출되지 않습니다.
- 이 프로젝트는 우선 심박수 중심으로 만들었지만, 같은 구조로 수면, 스트레스, HRV까지 쉽게 확장할 수 있습니다.
