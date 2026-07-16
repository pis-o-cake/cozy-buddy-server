# Cozy Buddy Server

자가호스팅 스마트홈 음성 AI 비서 서버. **설계서 `cozy-buddy-design-v3.md`(워크스페이스 `../docs/`)가 아키텍처·프로토콜·정책의 단일 진실원본** — 구현 전 해당 섹션을 먼저 확인한다.

## Git
- **커밋 메시지는 전부 영어로 작성한다** (subject·body 모두. 한국어 금지).
- 형식: `<type>(<scope>): <subject>` — subject는 대문자 시작·명령형·50자 이내·마침표 없음. body는 WHAT/WHY, 72자/줄.
- types: `feat` `fix` `build` `chore` `ci` `docs` `style` `refactor` `test`
- **Co-Authored-By 라인 금지** — 사용자 계정 단독 커밋.

## 아키텍처 규칙 (요약 — 상세는 설계서 §번호)
- **Package-by-Feature** (§6-1): `app/domain/<name>/{api,service,crud,schemas,models}.py`. 레이어별 패키징 금지. 라우터는 `domain/*/api.py` 자동 스캔.
- **교체 가능 요소는 전부 추상화** (§3): STT/TTS/LLM/IoT 어댑터 = ABC + `ProviderRegistry` + `.env` 키. 새 구현 추가 시 코어 무수정.
- **LLM tool loop** (§7-3): tool 결과는 `role:"tool"` + `tool_call_id` 표준 주입. 최종 응답은 마지막 루프 턴에서 스트리밍 — 재호출식 이중 생성 금지.
- **DB** (§6-2): PostgreSQL 16 + SQLAlchemy 2.0 async + Alembic. 스키마 변경은 반드시 Alembic 리비전으로.
- **로그는 영어 하드코딩**(loguru), 사용자 응답 문구는 `locales/ko.json` — 로그에 언어팩 사용 금지.
- **비밀정보**: `.env` + pydantic-settings. API 키·자격증명 하드코딩 금지, 로그 마스킹.
