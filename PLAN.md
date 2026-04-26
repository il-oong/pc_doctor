# PC Doctor — 자동 시스템 헬스 체크 툴 설계 플랜

> 라이트 의료(Light Medical) 테마 기반 데스크톱 진단 도구
> Stack: **Python 3.10+ / Tkinter (ttk) / psutil**

---

## 1. 제품 컨셉

PC를 환자처럼 다루는 "주치의(主治醫)" 컨셉의 진단 도구.
사용자가 앱을 실행하면 자동으로 **건강 검진(Health Check)** 을 수행하고,
**바이탈 사인(Vital Signs)** 을 카드 형태로 보여주며,
이상 항목에 대해서는 **처방전(Prescription)** 형태로 권장 조치를 제시한다.

핵심 가치:
- 비전문가도 한눈에 PC 상태를 이해 가능 (점수·색상·아이콘)
- 백그라운드 자동 진단 + 임계치 초과 시 알림
- 진단 결과를 의료 차트 스타일 리포트로 저장/공유

---

## 2. 라이트 의료 테마 — 디자인 토큰

병원 진료실의 청결하고 차분한 분위기를 그대로 옮긴다. 흰 바탕 + 한 가지 강조 컬러(진료 청록/블루) + 상태별 시그널 컬러.

### 2.1 컬러 팔레트
| 토큰 | HEX | 용도 |
| --- | --- | --- |
| `bg.canvas` | `#F7FAFC` | 메인 배경 (살짝 푸른 화이트) |
| `bg.surface` | `#FFFFFF` | 카드/패널 배경 |
| `bg.subtle` | `#EEF3F7` | 구분선·인풋 |
| `text.primary` | `#1F2D3D` | 본문 |
| `text.secondary` | `#5A6B7B` | 보조 |
| `text.muted` | `#8FA0B0` | 캡션 |
| `accent.primary` | `#2E7DD7` | 의료 블루 (버튼·헤더 강조) |
| `accent.soft` | `#E6F0FB` | 액센트 배경 |
| `state.healthy` | `#2BB673` | 정상 (민트 그린) |
| `state.warning` | `#F5A623` | 주의 (앰버) |
| `state.critical` | `#E5484D` | 위험 (코랄 레드) |
| `state.info` | `#3FA5C4` | 정보 |
| `divider` | `#E3EAF1` | 1px 분리선 |

### 2.2 타이포그래피
- 기본: `Segoe UI` (Win) / `SF Pro Text` (macOS) / `Pretendard`·`Noto Sans KR` (KR fallback)
- 스케일: 28 / 20 / 16 / 14 / 12
- 헤더는 SemiBold, 본문은 Regular

### 2.3 형태·레이아웃
- 카드: `radius 12`, `border 1px #E3EAF1`, `shadow 0 1px 2px rgba(15,23,42,.04)`
- 8px 베이스 스페이싱 그리드
- 아이콘: 의료 메타포 (heartbeat / stethoscope / thermometer / pulse / pill)
  - Tkinter는 비트맵 한계가 있으므로 PNG 아이콘셋(24/32px) 동봉 + `PIL.ImageTk` 로딩

### 2.4 Tkinter 적용 전략
- `tkinter.ttk` 의 `Style` 으로 토큰 매핑 (`Card.TFrame`, `Title.TLabel`, `Healthy.TLabel`...)
- 라운드 카드는 `tk.Canvas` 위에 `create_rounded_rect` 헬퍼로 구현 (ttk가 radius 미지원)
- 다크모드는 v1 범위 외 (라이트 전용)

---

## 3. 기능 범위 (검진 항목)

각 검진은 `Check` 베이스 클래스 구현체. 점수(0~100)·상태(healthy/warning/critical)·메시지·세부 데이터·권장 조치를 반환.

| 카테고리 | 검진 항목 | 핵심 지표 |
| --- | --- | --- |
| **CPU** | CPU 부하·코어별 사용률·로드 애버리지 | `psutil.cpu_percent`, `getloadavg` |
| **메모리** | RAM 사용률·스왑 사용량 | `psutil.virtual_memory`, `swap_memory` |
| **저장소** | 파티션별 사용률·여유 공간·읽기쓰기 IO | `psutil.disk_usage`, `disk_io_counters` |
| **네트워크** | 인터넷 연결·DNS·핑 RTT·인터페이스 상태 | `socket`, `subprocess(ping)`, `psutil.net_if_stats` |
| **배터리** | 잔량·충전 상태·배터리 헬스 (가능 시) | `psutil.sensors_battery` |
| **온도/팬** | CPU/디스크 온도·팬 RPM (OS 한정) | `psutil.sensors_temperatures`, `sensors_fans` |
| **프로세스** | 상위 자원 점유 프로세스·좀비 프로세스 수 | `psutil.process_iter` |
| **부팅/가동시간** | 업타임·부팅 시각 | `psutil.boot_time` |
| **OS·업데이트** | OS 버전·아키텍처·(Win) WUA 체크 옵션 | `platform`, OS별 어댑터 |

### 3.1 점수 산정
- 항목 점수 = 임계치 기반 선형 매핑 (예: CPU 사용률 ≤60% → 100, ≥95% → 0)
- **종합 헬스 스코어** = 가중 평균 (CPU·RAM·Disk 0.2씩, Network 0.15, Battery·Temp·Process·Uptime·OS 합 0.25)
- 상태 구간: 90+ 정상 / 70–89 주의 / <70 위험

---

## 4. UI 구조 — "진료실 레이아웃"

```
┌──────────────────────────────────────────────────────────┐
│  [PC Doctor 로고]   환자: DESKTOP-XYZ    [⟳ 재검진] [⚙] │  ← Header (56px, accent.primary 보더 1px)
├──────────┬───────────────────────────────────────────────┤
│ 사이드바  │  ┌──────── 종합 헬스 스코어 ─────────┐      │
│ (180px)  │  │   ❤  82 / 100   상태: 주의           │      │
│          │  │   체온계 게이지 + 한 줄 코멘트       │      │
│ • 대시보드│  └──────────────────────────────────────┘      │
│ • CPU    │  ┌──── 바이탈 사인 (3xN 카드 그리드) ──┐      │
│ • 메모리 │  │ [CPU 35%] [RAM 62%] [Disk 88%]      │      │
│ • 저장소 │  │ [Net 정상] [Battery 91%] [Temp 65℃] │      │
│ • 네트워크│ └──────────────────────────────────────┘      │
│ • 배터리 │  ┌──── 처방전 (Prescription) ──────────┐      │
│ • 온도   │  │ ⚠ 디스크 C: 88% — 임시파일 정리 권장│      │
│ • 프로세스│ │ ⚠ 메모리 부족 — 백그라운드 앱 종료  │      │
│ • 리포트 │  └──────────────────────────────────────┘      │
│          │                                                 │
├──────────┴───────────────────────────────────────────────┤
│  마지막 검진: 14:02:11   다음 자동검진: 14:32   ● 정상   │  ← Footer
└──────────────────────────────────────────────────────────┘
```

### 4.1 화면 (View) 목록
1. **Dashboard** — 종합 점수 + 바이탈 카드 + 상위 권장 조치 3개
2. **Detail View** (사이드바 항목별) — 시계열 그래프 + 상세 메트릭 표
3. **Report View** — 의료 차트 스타일 리포트 (Export PDF/HTML)
4. **History** — 과거 검진 결과 타임라인 (SQLite 저장)
5. **Settings** — 자동검진 주기, 알림 임계치, 시작 시 자동 실행

### 4.2 핵심 위젯
- `HealthScoreGauge` — Canvas로 그린 반원 게이지 (체온계 모티프 옵션)
- `VitalCard` — 아이콘 + 메트릭 큰 글씨 + 상태 배지
- `PrescriptionItem` — 약 처방 라인 스타일 (좌측 색상 바 + 메시지 + "조치" 링크)
- `ScanProgressBar` — 검진 진행 상태 (각 검진 단위로 step)
- `Sparkline` — 카드 우측 하단 미니 추이 그래프

---

## 5. 자동 검진 (Auto Scan) 동작

- **앱 시작 시**: Quick Scan (≤2초, 무거운 검진 제외) 자동 수행
- **주기 검진**: 사용자 설정(기본 30분)마다 Full Scan, `threading.Timer` + 종료 시 cancel
- 모든 검진은 워커 스레드에서 실행 → `queue.Queue` 로 결과 전달 → `root.after` 폴링으로 UI 업데이트 (Tkinter는 단일 스레드 전제)
- Critical 발생 시 시스템 트레이/토스트 알림
  - Windows: `winotify` (옵션 의존성)
  - macOS: `osascript`
  - Linux: `notify-send`

---

## 6. 아키텍처 / 파일 구조

```
pc_doctor/
├── main.py                         # 엔트리포인트
├── requirements.txt
├── PLAN.md                         # 본 문서
├── README.md
├── assets/
│   └── icons/                      # PNG 아이콘셋 (heart, cpu, ram, disk ...)
├── core/
│   ├── __init__.py
│   ├── checks/
│   │   ├── __init__.py             # registry + discovery
│   │   ├── base.py                 # Check, CheckResult, Severity
│   │   ├── cpu.py
│   │   ├── memory.py
│   │   ├── disk.py
│   │   ├── network.py
│   │   ├── battery.py
│   │   ├── temperature.py
│   │   ├── process.py
│   │   ├── uptime.py
│   │   └── os_info.py
│   ├── scheduler.py                # quick / full scan, periodic timer
│   ├── score.py                    # 종합 점수 계산
│   ├── report.py                   # 리포트(JSON/HTML/PDF) 생성
│   └── storage.py                  # SQLite 히스토리
├── ui/
│   ├── __init__.py
│   ├── app.py                      # Tk root, 라우팅
│   ├── theme.py                    # 토큰 → ttk Style 매핑
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── score_gauge.py
│   │   ├── vital_card.py
│   │   ├── prescription.py
│   │   ├── sparkline.py
│   │   └── rounded.py              # Canvas 라운드 헬퍼
│   └── views/
│       ├── __init__.py
│       ├── dashboard.py
│       ├── detail.py
│       ├── report.py
│       ├── history.py
│       └── settings.py
└── utils/
    ├── __init__.py
    ├── platform.py                 # OS 분기 헬퍼
    ├── format.py                   # bytes/percent/duration 포매팅
    └── notify.py                   # 크로스 플랫폼 알림 어댑터
```

### 6.1 핵심 인터페이스 (의사 코드)
```python
# core/checks/base.py
class Severity(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class CheckResult:
    key: str                # "cpu"
    title: str              # "CPU 부하"
    score: int              # 0..100
    severity: Severity
    summary: str            # 한 줄 설명
    metrics: dict           # 상세 수치
    recommendations: list[str]
    duration_ms: int

class Check(Protocol):
    key: str
    title: str
    weight: float
    quick: bool             # quick scan 포함 여부
    def run(self) -> CheckResult: ...
```

```python
# core/scheduler.py
class Scanner:
    def __init__(self, checks: list[Check], on_result, on_done): ...
    def quick_scan(self): ...   # quick=True 만 실행
    def full_scan(self): ...    # 전체 실행
    def start_periodic(self, interval_sec: int): ...
    def stop(self): ...
```

---

## 7. 의존성

`requirements.txt`
```
psutil>=5.9
Pillow>=10.0
```

선택 의존성 (런타임 미발견 시 graceful fallback):
- `winotify` (Windows 토스트 알림)
- `reportlab` (PDF 리포트)

표준 라이브러리: `tkinter`, `sqlite3`, `threading`, `queue`, `socket`, `platform`, `subprocess`

---

## 8. 단계별 구현 로드맵

| 단계 | 산출물 | 예상 분량 |
| --- | --- | --- |
| **Phase 1 — 스켈레톤** | 메인 윈도우 + 라이트 의료 테마 적용 + Dashboard 빈 레이아웃 + 더미 카드 | 1차 PR |
| **Phase 2 — 코어 검진** | `CPU/Memory/Disk` Check 구현 + Quick Scan + VitalCard 실데이터 바인딩 | 1차 PR |
| **Phase 3 — 확장 검진** | `Network/Battery/Temperature/Process/Uptime/OS` 추가 + Full Scan | 1차 PR |
| **Phase 4 — 점수·처방전** | `score.py` + Prescription UI + 헬스 게이지 게이지 위젯 완성 | 1차 PR |
| **Phase 5 — 자동화·히스토리** | 주기 검진 스케줄러 + SQLite 저장 + History View + 알림 | 1차 PR |
| **Phase 6 — 리포트·패키징** | HTML/PDF 리포트 + PyInstaller 패키징 + 아이콘/메타데이터 | 1차 PR |

각 Phase는 독립 PR 단위로 머지 가능한 형태로 분리.

---

## 9. 리스크 & 결정 사항

- **Tkinter 라운드/그림자 한계** → Canvas 헬퍼로 우회. 충분치 않으면 `customtkinter` 도입을 Phase 1 회고 시 재검토.
- **온도/팬 센서** → Linux는 `psutil.sensors_temperatures` 가능, Windows는 OEM 의존(데이터 없을 때 카드 비활성).
- **PDF 리포트** → `reportlab` 무거움. 1차는 HTML export, PDF는 Phase 6 옵션.
- **다국어(i18n)** → v1은 한국어 우선, 영어 리소스 키만 분리해 후속 확장 여지 확보.
- **테스트** → 각 Check는 `psutil` 의존 → `pytest` + monkeypatch로 결정론적 테스트. UI는 스모크만.

---

## 10. 다음 액션

플랜 승인 후 Phase 1(스켈레톤 + 테마)부터 별도 작업으로 착수.
