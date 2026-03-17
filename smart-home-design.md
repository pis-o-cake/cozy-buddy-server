# 스마트홈 AI 프로젝트 설계

## 1. 시스템 구성

### 1-1. 프로젝트 구성

| 프로젝트 | 기술 | 설명 |
|---------|------|------|
| **server** | FastAPI (Python) | LLM + TTS + STT + IoT 제어 서버 |
| **ai-hub** | Kotlin + Compose | Android 태블릿 AI 허브 앱 |
| **mobile** | Flutter | iOS/Android 외부 제어 앱 (후순위) |

### 1-2. 기술 스택

| 영역 | 기술 | 비고 |
|------|------|------|
| LLM | vLLM + Llama 3.1 8B → 추후 32B (맥미니) | Tool Calling 지원 |
| TTS | Piper TTS (한국어) | CPU 구동, 저지연 |
| STT | Faster-Whisper (small/medium) | GPU 구동 |
| 웨이크워드 | OpenWakeWord | CPU, 상시 대기 |
| 서버 | FastAPI + WebSocket | 비동기 |
| IoT | python-kasa (Tapo) | 로컬 LAN 제어 |
| Android | Kotlin + Compose + OkHttp/WebSocket | 네이티브 |
| DB | SQLAlchemy 2.0 + SQLite (→ PostgreSQL) | |
| 배포 | 개발: RTX 5080 PC / 운영: 맥미니 M4 Pro 32GB | |

### 1-3. 하드웨어

**개발 서버 (PC)**
- AMD Ryzen 7 7800X3D 8-Core (4.20 GHz)
- 32GB RAM
- RTX 5080 (16GB VRAM)

**운영 서버 (맥미니)**
- Mac Mini M4 Pro 32GB (예정)
- llama.cpp (Metal) + 32B 모델

### 1-4. VRAM 사용 계획 (개발 PC 기준)

| 모델 | VRAM | 구동 |
|------|------|------|
| Llama 3.1 8B Q4 | ~5GB | GPU |
| Faster-Whisper small | ~1GB | GPU |
| Piper TTS | ~0.2GB | CPU |
| OpenWakeWord | ~0.05GB | CPU |
| **합계** | **~6.3GB** | 16GB 중 여유 |

---

## 2. 아키텍처

### 2-1. 전체 아키텍처

```
┌─────────────────────────────────────────────┐
│                 로컬 PC (서버)                │
│  ┌──────────┐ ┌────────┐ ┌──────────────┐   │
│  │ vLLM     │ │ Piper  │ │ Whisper STT  │   │
│  │ Llama 8B │ │ TTS    │ │              │   │
│  │ (GPU)    │ │ (CPU)  │ │ (GPU)        │   │
│  └────┬─────┘ └───┬────┘ └──────┬───────┘   │
│       └─────┬─────┘             │            │
│       ┌─────▼─────┐    ┌───────▼────────┐   │
│       │  FastAPI   │    │ OpenWakeWord   │   │
│       │  메인 서버  │    │ (CPU, 상시)    │   │
│       └─────┬─────┘    └───────┬────────┘   │
│             │                  │             │
│       ┌─────▼──────────────────▼────────┐    │
│       │      WebSocket Gateway          │    │
│       └─────┬───────────────────────────┘    │
│             │              │                 │
│    ┌────────▼───┐  ┌──────▼──────┐          │
│    │ python-kasa│  │  외부 API    │          │
│    │ Tapo 제어  │  │ 날씨/뉴스 등 │          │
│    └────────────┘  └─────────────┘          │
└──────────────┬──────────────────────────────┘
               │ WiFi (LAN)
     ┌─────────▼─────────┐
     │  Android 태블릿    │
     │  (AI 허브 UI)      │
     └───────────────────┘
```

### 2-2. 데이터 흐름

```
[WebSocket 요청]
    │
    ▼
api.py (라우터)
    │ 오디오 or 텍스트 수신
    ▼
voice/stt_service.py (음성→텍스트)
    │
    ▼
llm/service.py
    │ ← prompts/system.py (시스템 프롬프트)
    │ ← tools/ (사용 가능 도구)
    │
    ├─→ [일반 대화] → 텍스트 응답
    │
    └─→ [Tool Call 감지]
         │
         ▼
    tools/registry.py (디스패치)
         │
         ▼
    tools/device_tools.py
         │
         ▼
    device/service.py
         │
         ▼
    device/adapters/tapo.py
         │ python-kasa → 실제 장치 제어
         ▼
    결과 → LLM에 재전달 → 최종 응답 생성
         │
         ▼
voice/tts_service.py (텍스트→음성)
         │
         ▼
    WebSocket으로 오디오 응답 전송
```

### 2-3. 웨이크워드 흐름 (Android)

```
상시 대기 (저전력)
    │
    ▼ "헤이 ○○" 감지
    │
마이크 활성화 + UI 전환 (듣는 중)
    │
    ▼ 무음 감지 (1.5초) → 녹음 종료
    │
오디오 → 서버 WebSocket 전송
    │
    ▼ STT → LLM → TTS
    │
응답 오디오 수신 + 재생
    │
    ▼ 재생 완료
    │
다시 상시 대기
```

---

## 3. 서버 패키지 구조 (도메인 기반)

```
server/
├── pyproject.toml
├── .env
├── docker-compose.yml
│
├── app/
│   ├── main.py                    ← FastAPI 앱, 라우터 자동 등록
│   ├── config.py                  ← pydantic-settings
│   │
│   ├── core/                      ← 공통 (전 도메인 공유)
│   │   ├── exceptions.py
│   │   ├── logging.py
│   │   ├── database.py            ← engine, session, Base
│   │   ├── websocket.py           ← WS 매니저
│   │   └── constants.py
│   │
│   ├── domain/                    ← 도메인별 독립 패키지
│   │   │
│   │   ├── chat/                  ← 대화 도메인
│   │   │   ├── api.py
│   │   │   ├── service.py
│   │   │   ├── schemas.py
│   │   │   ├── models.py
│   │   │   └── crud.py
│   │   │
│   │   ├── llm/                   ← LLM 도메인
│   │   │   ├── service.py
│   │   │   ├── schemas.py
│   │   │   ├── prompts/
│   │   │   │   ├── system.py
│   │   │   │   └── templates.py
│   │   │   └── tools/
│   │   │       ├── registry.py
│   │   │       ├── device_tools.py
│   │   │       ├── scenario_tools.py
│   │   │       └── info_tools.py
│   │   │
│   │   ├── voice/                 ← 음성 도메인
│   │   │   ├── api.py
│   │   │   ├── tts_service.py
│   │   │   ├── stt_service.py
│   │   │   ├── wake_service.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── device/                ← IoT 장치 도메인
│   │   │   ├── api.py
│   │   │   ├── service.py
│   │   │   ├── schemas.py
│   │   │   ├── models.py
│   │   │   ├── crud.py
│   │   │   └── adapters/
│   │   │       ├── base.py        ← DeviceAdapter (ABC)
│   │   │       ├── tapo.py
│   │   │       └── ir.py
│   │   │
│   │   └── scenario/              ← 시나리오 도메인
│   │       ├── api.py
│   │       ├── service.py
│   │       ├── schemas.py
│   │       ├── models.py
│   │       ├── crud.py
│   │       └── scheduler.py
│   │
│   └── middleware/
│       ├── error_handler.py
│       └── request_logger.py
│
└── tests/
    ├── domain/
    │   ├── chat/
    │   ├── llm/
    │   ├── voice/
    │   ├── device/
    │   └── scenario/
    └── conftest.py
```

### 도메인 간 의존성 규칙

```
chat  ──→  llm  ──→  tools  ──→  device
  │                               scenario
  └──→  voice (STT/TTS)

✅ chat → llm, voice 참조 OK
✅ llm → tools → device/scenario 참조 OK
❌ device → chat 참조 금지 (역방향)
❌ voice → llm 참조 금지 (역방향)
→ 순환 참조 발생 시 core/로 인터페이스 추출
```

### 라우터 자동 등록

- `domain/*/api.py` 자동 탐색
- `/api/{도메인명}` 엔드포인트 자동 등록
- `api.py` 추가만으로 라우팅 완료, `main.py` 수정 불필요

### 확장 시 (폴더 추가만)

```
domain/
├── weather/       ← 날씨
├── music/         ← 음악 재생
├── notification/  ← 알림
└── rag/           ← RAG 검색
```

---

## 4. DB 스키마

### conversations

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | PK | |
| role | str | user/assistant/tool |
| content | TEXT | 메시지 내용 |
| tool_call | JSON (nullable) | Tool Call 데이터 |
| created_at | datetime | |

### devices

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | PK | |
| name | str | 거실 조명 |
| device_type | str | light/plug/sensor |
| adapter_type | str | tapo/ir |
| location | str | 거실/침실 |
| config | JSON | IP, 인증 등 |
| is_active | bool | |

### scenarios

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | PK | |
| name | str | 영화 모드 |
| actions | JSON | [{device, action, value}] |
| trigger | str | manual/schedule/voice |

---

## 5. Tool Calling 구조

### System Prompt 구성

```
너는 스마트홈 AI 비서.
사용 가능 함수:
- control_device(device_name, action, value)
- get_device_status(device_name)
- activate_scenario(scenario_name)

등록된 장치:
- "거실 조명" (Tapo L530, 조명)
- "침실 조명" (Tapo L510, 조명)
- "선풍기" (Tapo P100, 플러그)
→ 장치 추가/삭제 시 프롬프트 자동 갱신
```

### Tool Registry 패턴

- 데코레이터로 함수 등록 → LLM 호출 가능 도구로 자동 등록
- `@ToolRegistry.register("turn_off")` 형태

### 흐름 예시

```
"거실 불 좀 어둡게 해줘"
  → STT → 텍스트
  → LLM 판단 → {"function":"set_brightness","args":{"device":"거실 조명","brightness":30}}
  → 서버 파싱 → python-kasa → Tapo 제어
  → 결과 → LLM → "거실 조명을 30%로 낮췄어요"
  → TTS → 스피커
```

---

## 6. 개발 로드맵

### Phase 0: 서버 인프라 (2주)

**Week 1: LLM 서버**
- [ ] Poetry 프로젝트 + Docker Compose 기본 구조
- [ ] vLLM 설치 + Llama 8B 로드
- [ ] FastAPI `/api/chat` 엔드포인트 (스트리밍)
- [ ] Tool Calling 프로토타입 (system prompt + JSON 파싱)
- [ ] curl 통합 테스트

**Week 2: TTS + STT + 웨이크워드**
- [ ] Piper TTS 한국어 모델 + `/api/tts`
- [ ] Faster-Whisper GPU + `/api/stt` (WAV→텍스트)
- [ ] OpenWakeWord 기본 모델 테스트
- [ ] 전체 파이프라인 통합 (웨이크→STT→LLM→TTS)
- [ ] WebSocket 게이트웨이 구축

### Phase 1: 스마트홈 장치 제어 (2주)

**Week 3: Tapo 연동**
- [ ] Tapo 장치 구매/설정 (조명 L530, 플러그 P100)
- [ ] python-kasa 장치 검색, 상태 조회, on/off 테스트
- [ ] DeviceService + DeviceAdapter 패턴 구현
- [ ] Tool Calling ↔ DeviceService 매핑
- [ ] 통합 테스트 ("거실 불 30%로" → 실제 제어)

**Week 4: 시나리오 + 스케줄링**
- [ ] 시나리오 엔진 ("영화 모드" → 조명 10% + 색상)
- [ ] 시나리오 Tool 등록
- [ ] APScheduler 스케줄링 ("밤 11시 전체 소등")
- [ ] 대화 컨텍스트 (SQLite + 최근 N턴 유지)
- [ ] 에러 핸들링 (장치 오프라인, 타임아웃, 재시도)

### Phase 2: Android AI 허브 (4주)

**Week 5~6: 코어 통신 + 기본 UI**
- [ ] WebSocket 클라이언트 (OkHttp, 재연결)
- [ ] Repository 패턴 (ChatRepository, DeviceRepository)
- [ ] HubViewModel (대화/장치/연결 상태)
- [ ] 메인 화면 (네스트허브 스타일: 시계, 날씨, 장치 카드)
- [ ] 대화 화면 (듣는 중 → 처리 중 → 응답 애니메이션)
- [ ] 오디오 녹음 (AudioRecord → PCM → 서버 전송)
- [ ] 오디오 재생 (서버 TTS → MediaPlayer)

**Week 7: 웨이크워드 온디바이스**
- [ ] Porcupine 또는 OpenWakeWord ONNX 온디바이스
- [ ] 상시 마이크 → 웨이크 감지 → 녹음 → 서버 전송
- [ ] Foreground Service + 배터리 최적화

**Week 8: 폴리싱**
- [ ] 장치 제어 UI (카드 터치 직접 제어)
- [ ] 시나리오 UI (원터치 버튼)
- [ ] 에러 UI (연결 끊김, 장치 오프라인)
- [ ] 항상 켜짐 모드 (KEEP_SCREEN_ON + 밝기 자동)
- [ ] 앰비언트 모드 (포토프레임)

### Phase 3: 맥미니 이관 + 안정화 (2주)

**Week 9: 맥미니 배포**
- [ ] macOS 환경 세팅
- [ ] llama.cpp Metal → Llama 3.1 32B Q4
- [ ] 성능 벤치마크 (첫 토큰, tokens/sec)
- [ ] TTS/STT 이관

**Week 10: 안정화**
- [ ] LaunchDaemon 자동 시작
- [ ] 헬스체크 + 자동 재시작
- [ ] loguru 파일 로테이션
- [ ] 고정 IP + mDNS (smarthome.local)

### Phase 4: 고도화 (선택, 각 1~2주)

| 기능 | 우선순위 |
|------|---------|
| 날씨/뉴스 API (Tool Calling) | 상 |
| RAG (ChromaDB + bge-m3) | 중 |
| LoRA 파인튜닝 (말투/행동 패턴) | 중 |
| 커스텀 웨이크워드 (내 목소리) | 중 |
| Flutter 외부 제어 앱 | 하 |
| 음악 재생 (Spotify/YT) | 하 |
| 가전 확장 (에어컨, TV, 커튼) | 하 |

### 타임라인

```
Week  1-2   ██████████  Phase 0: 서버 인프라
Week  3-4   ██████████  Phase 1: Tapo + Tool Calling
Week  5-8   ████████████████████  Phase 2: Android 허브
Week  9-10  ██████████  Phase 3: 맥미니 + 안정화
Week  11~   ░░░░░░░░░░  Phase 4: 고도화
```

**핵심 MVP: ~10주 (2.5개월)**
