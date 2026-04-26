# 🩺 PC Doctor

라이트 의료 테마 기반 PC 자동 시스템 헬스 체크 툴.

## 실행

```bash
pip install psutil
python main.py
```

## 검진 항목

| 항목 | 설명 |
|------|------|
| CPU 부하 | 사용률·코어별·로드 애버리지 |
| 메모리 | RAM·스왑 사용량 |
| 저장소 | 파티션별 여유 공간 |
| 하드웨어 | 디스크 SMART/예측 실패 상태 (Win: WMI · *nix: smartctl) |
| Windows 점검 | 보류 업데이트, Defender 상태/정의/검사, 방화벽, 재부팅 대기 |
| 네트워크 | 인터넷 연결·DNS·RTT |
| 배터리 | 잔량·충전 상태 |
| 온도 | CPU 온도 센서 |
| 프로세스 | 자원 상위 프로세스·좀비 수 |
| 가동 시간 | 업타임 |
| 운영체제 | OS 버전·아키텍처 |

## 헬스 점수

- **90–100** 정상 (녹색)
- **70–89** 주의 (주황)
- **0–69** 위험 (빨강)

## 주요 기능

- 앱 시작 시 Quick Scan 자동 실행
- 검진 결과를 처방전(Prescription) 형식으로 표시
- **원클릭 조치**: 처방전의 `▶ 조치 실행` 버튼으로 추천 조치를 직접 수행
  (작업 관리자/디스크 정리/임시파일 삭제/DNS 캐시 비우기/Defender 검사/Windows Update 등)
- 주기 자동 검진 (기본 30분, 설정 가능)
- 검진 이력 SQLite 저장 (`~/.pc_doctor/history.db`)
- HTML 리포트 export (`~/.pc_doctor/reports/`)
- Critical 상태 시 데스크톱 알림

## 의존성

- Python 3.10+
- psutil ≥ 5.9
