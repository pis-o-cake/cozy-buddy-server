# cozy-buddy-server 정밀 분석 (설계 v2 대비)

- 분석 대상: `scratchpad/cozy-buddy-server` (로컬 레포, git 아님)
- 기준 문서: `D:/workspace/etc/cozy/docs/cozy-buddy-design-v2.md` §5 (서버 아키텍처)
- 분석일: 2026-07-16

---

## 1. 전체 패키지 구조 (실제 트리)

```
cozy-buddy-server/
├── pyproject.toml               # Poetry 2.x (package-mode=false), Python >=3.10,<3.13
├── Dockerfile                   # python:3.10-slim + poetry (uv 아님, gunicorn 없음)
├── docker-compose.yml           # server 1개 + vllm(주석 처리) + healthcheck
├── .env.example / .gitignore
├── smart-home-design.md         # 구버전(v1) 설계 문서 사본
│
├── app/
│   ├── main.py                  # 라우터 자동등록(pkgutil 스캔) + lifespan + /health
│   ├── config.py                # pydantic-settings (llm_default_provider 등)
│   ├── core/
│   │   ├── constants.py  database.py  exceptions.py
│   │   ├── i18n.py  logging.py  websocket.py
│   │   └── (없음: registry.py, security.py)        <- 설계 §5-2 대비 누락
│   ├── domain/
│   │   ├── chat/      api·service·crud·schemas·models (완전 5종)
│   │   ├── device/    api·service·crud·schemas·models + adapters/{base,tapo}
│   │   ├── llm/       api·service·schemas + adapters/{base,vllm,openai,gemini}
│   │   │              + prompts/{system,templates} + tools/{registry,device,info,scenario}
│   │   ├── rag/       api·service·schemas (DB 모델 없음 — ChromaDB 직접)
│   │   ├── scenario/  api·service·crud·schemas·models + scheduler.py
│   │   └── voice/     api·schemas + stt_service·tts_service·wake_service
│   ├── middleware/    error_handler.py  request_logger.py
│   └── locales/       ko.json (i18n 언어팩)
│
└── tests/
    ├── conftest.py (in-memory SQLite + httpx ASGI client)
    ├── test_core.py
    └── domain/{chat,device,llm,rag,scenario}/test_*.py   # voice/ 는 __init__.py만
```

### 설계 v2 §5-2 구조와 비교

| 설계 v2 항목 | 실제 | 판정 |
|---|---|---|
| 도메인 기반 패키징 (P6, api·service·crud·schemas·models 자족) | 동일 구조 | **일치** |
| 라우터 자동등록 (`domain/*/api.py` 스캔 → `/api/<domain>`) | `main.py::_register_domain_routers` 구현 | **일치** |
| `core/registry.py` (범용 Provider 레지스트리) | 없음 | **불일치(누락)** |
| `core/security.py` (JWT/페어링 토큰) | 없음 | **불일치(누락)** |
| `domain/auth/` (페어링·토큰 발급) | 도메인 자체 없음 | **불일치(누락)** |
| `voice/providers/` + `stt_base.py`(ABC) + `factory.py` | 구체 서비스 3개(stt/tts/wake), ABC·factory 없음 | **불일치** |
| voice에서 웨이크워드 제거 (P5: 온디바이스) | `wake_service.py` 서버에 존재(스텁) | **불일치(v1 잔재)** |
| `device/taxonomy.py` (DeviceType/Capability) | 없음 (`constants.py`에 상수 3개뿐) | **불일치(누락)** |
| device adapters: tapo + matter + homeassistant + ir | tapo(스텁) 1개만 | **불일치** |
| llm adapters vllm/openai/gemini + prompts + tools | 전부 존재 | **일치** |
| scenario + 스케줄러 | 존재하나 스케줄러 스텁 | **부분 일치** |
| chat (세션·컨텍스트·요약) | 컨텍스트만. hub_id 세션/롤링 요약 없음 | **부분 일치** |
| rag | v2 §5-2엔 명시 없음(Phase 4 항목)이나 **완성돼 있음** | 설계보다 선행 구현 |

---

## 2. 도메인별 구현 상태 판정

| 도메인 | 판정 | 핵심 클래스/ABC | 비고 |
|---|---|---|---|
| **core** | 구현 완료(현 범위) | `Base`, `get_db`, `WebSocketManager`, `CozyBuddyError` 계열 5종, `t()`(i18n), `setup_logging` | registry/security 누락. `WebSocketManager`는 단순 연결 리스트(허브 식별 없음) |
| **device** | **부분 구현** | `DeviceAdapter(ABC)`: connect/disconnect/turn_on/turn_off/get_status/execute · `TapoAdapter` · `DeviceService` · `Device`(모델) | CRUD/API/서비스 골격 완성. **TapoAdapter는 python-kasa 미연동 스텁**(전부 `# TODO`, 로그만 찍고 성공 반환). `discover()/identify()` 없음 |
| **scenario** | **부분 구현** | `ScenarioService`, `ScenarioScheduler`, `Scenario`(모델) | CRUD/API 완성. `activate_scenario`가 **액션 실제 실행 없이 카운트만 반환**(`# TODO: Execute actions via DeviceService`). 스케줄러는 APScheduler 미연동 스텁 |
| **llm** | **구현 완료(코어)** | `LLMAdapter(ABC)`: initialize/chat/chat_stream/shutdown · `VLLMAdapter`/`OpenAIAdapter`/`GeminiAdapter` · `LLMService` · `ToolRegistry` | 3개 어댑터 모두 OpenAI 호환 클라이언트로 동작 코드 완성. tool 5종 등록(control_device, get_device_status, activate_scenario, get_weather(스텁), search_knowledge) |
| **chat** | **구현 완료(텍스트 범위)** | `ChatService`(process_message / process_message_stream, MAX_TOOL_ITERATIONS=5), `Conversation`(모델) | tool calling 루프 + 스트리밍 + WS 완성. 단, **세션 개념 없음**(전역 단일 대화, hub_id/room/만료/롤링요약 없음) |
| **rag** | **구현 완료** | `RAGService`(ChromaDB PersistentClient + SentenceTransformer e5-small, 청크 분할/ingest/query/컬렉션 관리) | 실동작 코드. `search_knowledge` tool로 LLM에 연결됨 |
| **voice** | **스텁** | `STTService`/`TTSService`/`WakeWordService` (전부 `# TODO`) | faster-whisper/piper/openWakeWord 미연동. **ABC 없음** — provider 패턴 미적용. API는 파일 업로드 STT/TTS REST 2개뿐 |

---

## 3. Provider/Adapter 추상화 실태

### 3-1. LLM — 유일하게 "동작하는" 교체 구조
- `LLMAdapter(ABC)` → 3개 구현체. `LLMService.initialize()`가 **하드코딩 리스트**로 어댑터 생성:
  - vllm: 항상 시도 / openai·gemini: **API 키 존재 시에만** 활성화 (init 실패 시 warning 후 skip)
- 교체 지점: `.env`의 `LLM_DEFAULT_PROVIDER` + **요청별 `provider` 파라미터**(REST/WS body)로 런타임 전환 가능
- **설계와 차이**: v2 §5-3의 `_REGISTRY: dict[str, type] + build_xxx()` 팩토리 패턴이 아니라 서비스 내 하드코딩. 새 provider 추가 시 `LLMService.initialize()` 수정 필요 (설계 목표 "레지스트리 1줄"에 미달, 다만 실용상 유사)

### 3-2. Device — 절반짜리 레지스트리
- `_ADAPTER_MAP: dict[str, type[DeviceAdapter]] = {"tapo": TapoAdapter}` (service.py 모듈 레벨)
- 교체 지점: env가 아니라 **DB의 `Device.adapter_type` 컬럼** → 기기별 어댑터 선택 (설계 의도와 부합하는 방향)
- 어댑터는 **요청마다 생성·connect·disconnect** (커넥션 풀/캐시 없음)

### 3-3. Voice — 추상화 부재 (최대 갭)
- STT/TTS/Wake 모두 구체 클래스 직접 인스턴스화(`api.py` 모듈 레벨). `STT_PROVIDER`/`TTS_PROVIDER` env 자체가 없음
- 설계 v2의 `STTProvider(ABC)`/`TTSProvider(ABC)`/`factory.py` 전부 미구현

### 3-4. 공통
- `core/registry.py`(범용 레지스트리) 없음 → 도메인마다 제각각 방식
- DI: FastAPI `Depends()`는 DB 세션에만 사용. `llm_service`/`rag_service`는 **`app/main.py` 모듈 전역 싱글턴**을 `from app.main import llm_service`로 함수 내부 지연 임포트(순환참조 회피용) — Depends 주입 아님

---

## 4. LLM 통합 방식 · Tool Calling · WS 게이트웨이

### 4-1. LLM 통합 — Ollama 아님, vLLM(OpenAI 호환)
- **Ollama 래핑 없음.** 기본은 `VLLMAdapter`: vLLM의 OpenAI 호환 endpoint(`http://localhost:8080/v1`)를 `openai.AsyncOpenAI` 클라이언트로 호출
- Gemini도 OpenAI 호환 모드(`generativelanguage.googleapis.com/v1beta/openai/`) 사용 → **3개 어댑터가 사실상 동일한 OpenAI-SDK 코드 3벌 복붙** (베이스 클래스로 통합 여지 큼)
- 시스템 프롬프트는 `locales/ko.json`의 `prompt.system`에서 로드(i18n 준수), tools/devices 설명 주입식 — 단 `devices_description` 주입 호출부 없음(항상 "없음")

### 4-2. Tool Calling 구조
- `ToolRegistry`: **클래스 변수 dict + 데코레이터 등록** (`@ToolRegistry.register(name, description, parameters)`), import 부수효과로 등록
- 루프는 `ChatService.process_message`에 존재 (설계는 llm/service.py를 Orchestrator로 지정 — 위치 불일치, 기능은 동일):
  1. system prompt + 최근 20턴 컨텍스트 → `llm_service.chat(tools=…)`
  2. `tool_calls` 있으면 `ToolRegistry.execute` → 결과를 **`role:"user"` 메시지에 텍스트 템플릿으로 주입** (OpenAI 표준 `role:"tool"` + `tool_call_id` 미사용 — 비표준, 모델에 따라 품질 저하 소지)
  3. 최대 5회 반복(MAX_TOOL_ITERATIONS) 후 응답 저장
- 스트리밍 경로(`process_message_stream`): tool 루프는 논스트리밍으로 돌고, 종료 후 **동일 메시지로 LLM을 한 번 더 스트리밍 호출** → 최종 응답을 사실상 2회 생성(비용/지연 2배). 스트림 중 tool_call 델타는 어댑터가 무시

### 4-3. WS 게이트웨이 — 텍스트 채팅용만 존재
- `/api/chat/ws`: `{content, provider}` 수신 → `{type: chunk|done|error}` 송신. 이게 전부
- **설계 §4 프로토콜 미구현**: `utterance.start/end`, `stt.partial/final`, `state`, `tts.start/end`, 바이너리 오디오 프레임, `hub_id`/`room`/`session_id` 전부 없음
- `core/constants.py`에 WS_TYPE_AUDIO 등 상수만 예약돼 있고 사용처 없음
- 하트비트/재연결 백오프 정책(§4-3) 서버측 대응 없음

---

## 5. 테스트 / 도커 / 설정 상태

### 5-1. 테스트 — 양호 (voice 제외)
- pytest + pytest-asyncio(auto), in-memory SQLite, httpx ASGI 클라이언트 (conftest.py)
- 커버: core(예외/설정/상수), chat(CRUD·tool 루프·스트리밍·max iterations — 277줄, 가장 충실), device(CRUD·어댑터·서비스), llm(레지스트리·프롬프트·스키마·서비스 에러), rag(ingest/query/컬렉션/청크분할), scenario(CRUD·활성화)
- **공백**: voice 테스트 0건(디렉토리만), LLM 어댑터 실호출 mock 테스트 없음, WS 엔드포인트 테스트 없음

### 5-2. 도커 — 존재하나 규칙/스택과 어긋남
- `Dockerfile`: **python:3.10-slim** (권장 3.12-slim 아님) + pip로 poetry 설치 후 `poetry install` (권장 uv 아님). uvicorn 단독 CMD — **gunicorn+uvicorn worker 프로덕션 구성 없음**, Nginx/Caddy 리버스프록시 없음
- python-kasa extra는 `python_version>='3.11'` 조건 → **3.10 이미지에선 IoT extra 설치 불가** (버전 모순)
- `docker-compose.yml`: healthcheck 있음, vLLM 서비스는 주석 슬롯. GPU passthrough 예시 포함
- `poetry.lock` 없음 (레포에 미포함)

### 5-3. 설정
- `.env.example` + pydantic-settings 정상. LLM 3사 키/모델, RAG, STT/TTS 모델 경로 노출
- **없음**: `STT_PROVIDER`/`TTS_PROVIDER`(voice 교체 env), JWT/시크릿, hub/room 관련, Tailscale/보안 관련 설정
- i18n: `locales/ko.json` 단일 — 에러 메시지·프롬프트·스텁 문구 분리 (규칙 준수). 로그는 영어 하드코딩 (준수)

---

## 6. 설계 v2 대비 갭 목록 (우선순위순)

### A. 미구현 (설계에 있으나 코드 없음)
1. **음성 WS 게이트웨이(§3·§4)** — 오디오 스트리밍 프로토콜, 바이너리 프레임, stt.partial/tts 스트림, 세션 상태머신. **제1 목적(음성 IoT 제어)의 경로 자체가 부재**
2. **voice provider 추상화(§5-3)** — STTProvider/TTSProvider ABC + factory + env 교체. 현재는 스텁 구체 클래스
3. **STT/TTS 실연동** — faster-whisper, piper 미통합 (pyproject에 optional deps만 선언)
4. **auth 도메인 + core/security.py(§7)** — 페어링/device token/JWT 골격 전무
5. **멀티룸/멀티허브(§2)** — hub_id/room 개념이 서버 어디에도 없음. Device 모델은 `location` 문자열만(설계의 `room` 의미는 유사하나 해석 로직 없음)
6. **device taxonomy(§5-4)** — `taxonomy.py`, capabilities 필드, 기본 capability 프로파일 없음
7. **기기 등록 플로우(§5-4)** — discover()/identify()가 DeviceAdapter ABC에 없음. LAN 스캔/연결확인/등록→system prompt 갱신 없음
8. **Tapo 실제 제어** — python-kasa 미연동 (adapter 전부 TODO, 가짜 성공 응답)
9. **시나리오 실행부 + APScheduler** — activate가 액션 실행 안 함, 스케줄러 스텁
10. **세션 모델(§6)** — hub_id별 독립 세션, 10턴+롤링 요약, 3분 만료, user_id 필드 전부 없음
11. **실패 정책(§8)** — 기기 재시도/백오프, LLM 타임아웃 폴백, tool 루프 초과 안내 없음(루프 cap만 존재)
12. **core/registry.py** — 범용 provider 레지스트리 없음

### B. 설계와 다르게 구현된 부분
1. **wake_service.py가 서버에 존재** — v2 P5는 웨이크워드를 온디바이스(Android) 전용으로 이동, 서버에서 제거하기로 결정. v1 잔재
2. **tool 결과를 `role:"user"` 텍스트로 주입** — OpenAI 표준 `role:"tool"` 미사용. 어댑터가 OpenAI 호환인 만큼 표준 방식이 안전
3. **스트리밍 시 최종 응답 이중 생성** — tool 루프 완료 후 받은 응답을 버리고 같은 컨텍스트로 재호출·스트리밍 (지연·비용 2배, §9 SLA에 불리)
4. **tool 루프 위치** — 설계는 llm/service.py(Orchestrator), 실제는 chat/service.py. chat→llm 단방향이라 치명적이진 않으나 voice 파이프라인 추가 시 재사용 어려움
5. **LLM 어댑터 등록이 팩토리/레지스트리가 아닌 서비스 내 하드코딩** — provider 추가 시 코어 수정 필요
6. **전역 싱글턴 + 지연 임포트(`from app.main import llm_service`)** — Depends() DI 규칙 위배, 순환참조 냄새
7. **Dockerfile 3.10-slim + poetry** — python-kasa(>=3.11) extra와 모순, 규칙(3.12-slim + uv + gunicorn) 위배
8. **Device.location vs 설계의 room** — 명칭·역할(발화 허브 room 기준 해석) 불일치
9. **3개 LLM 어댑터 코드 중복** — OpenAI 호환 공통 베이스로 묶을 수 있는 90% 동일 코드 3벌

### C. 설계보다 앞서 있는 부분 (참고)
- **RAG 도메인 완성** (설계상 Phase 4 항목) — ChromaDB + e5-small + tool 연결까지 동작 수준
- 라우터 자동등록, i18n 언어팩, loguru, 미들웨어(에러/요청로그), 테스트 하네스는 규칙·설계 모두 충족

### 현재 위치 요약 (로드맵 §11 기준)
- **Phase 0**: 도메인 구조/자동등록/config OK, provider 레지스트리 부분(LLM만·비표준), WS 프로토콜 미구현, auth 미구현
- **Phase 1**: STT/TTS 미구현, LLM orchestrator+tool loop 완료(텍스트), e2e 에코 부분(텍스트 WS만)
- **Phase 2**: Tapo 실연동/room 모델/시나리오 실행·스케줄러/실패 정책 전부 미착수
- 종합: **"텍스트 챗봇 + IoT 골격"까지 완성, "음성 스마트홈 허브"는 미착수**