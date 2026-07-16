# Cozy Buddy Server

자가호스팅 스마트홈 음성 AI 비서 **Cozy Buddy**의 서버.
Google Nest Hub 2세대의 기능을 로컬 우선으로 커버하되, LLM 대화 품질로 차별화한다.

- **스택**: FastAPI · SQLAlchemy 2.0(async) + PostgreSQL 16 · faster-whisper(STT) · Supertonic 3(TTS) · 클라우드 LLM(Gemini/OpenAI/Claude) — 전 구성요소 provider/adapter 패턴으로 교체 가능
- **클라이언트**: Android 태블릿 허브(WebSocket 연결, 온디바이스 웨이크워드 "jarvis")
- **설계서**: [docs/cozy-buddy-design-v3.md](docs/cozy-buddy-design-v3.md) — 아키텍처·프로토콜·정책의 단일 진실원본 (기술 선정 근거: [docs/research/](docs/research/))

> 이전 구현은 [`legacy`](../../tree/legacy) 브랜치에 보존되어 있다. 본 main은 설계서 v3.4 기준 그린필드 재구현이다.
