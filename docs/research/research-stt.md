# cozy-buddy 서버측 한국어 STT 선정 조사

- **조사일:** 2026-07-16
- **대상 환경:** Windows 데스크톱, RTX 5080 16GB (Blackwell, sm_120), Ryzen 7 7800X3D, 32GB RAM
- **워크로드:** 스마트홈 음성 명령 (1~5초 짧은 발화, 한국어 우선, LAN 내 완결)
- **제약:** LLM(로컬)과 VRAM 동시 상주, provider 인터페이스로 교체 가능해야 함

---

## 결론 (요약)

| 구분 | 선정 | 비고 |
|---|---|---|
| **기본 채택** | **faster-whisper + large-v3-turbo (compute_type=float16)** | VRAM ~2GB, 3~5초 발화 0.2~0.5초 내 처리 예상, 한국어 상위권 품질 |
| 품질 상향 옵션 | faster-whisper + large-v3 (float16) | VRAM ~3.5GB, turbo 대비 한국어 소폭 우세 |
| 한국어 특화 옵션 | `ghost613/faster-whisper-large-v3-turbo-korean` (zeroth-korean 파인튜닝, CTranslate2 포맷) | 동일 코드로 모델 경로만 교체 |
| 교체 후보 1 (클라우드) | **CLOVA Speech (gRPC 실시간 스트리밍)** | 한국어 인식률 최상급, 진정한 partial 스트리밍 |
| 교체 후보 2 (클라우드) | ReturnZero VITO / Deepgram nova-3 / OpenAI gpt-4o-transcribe | 아래 상세 |
| 채택 보류 | sherpa-onnx 한국어 스트리밍 zipformer, NVIDIA Parakeet/Canary 최신판 | 품질/한국어 지원 문제 |

**핵심 주의:** RTX 5080(Blackwell)에서 CTranslate2 **INT8이 미지원** — CTranslate2 4.6.x에서 sm120 INT8이 비활성화됨(구버전은 `CUBLAS_STATUS_NOT_SUPPORTED` 크래시). **`compute_type="float16"` 필수.**

---

## 1. faster-whisper (large-v3 / turbo)

### 1.1 한국어 품질

- 한국어는 Whisper 계열의 "best-supported" 언어군(영·서·불·독·이·일·**한**·포·러)에 포함.
- rtzr의 한국어 STT 벤치마크(AI-Hub 6개 데이터셋 × 3,000문장, CER 기준)에서 OpenAI Whisper는 **평균 CER 11.34%** — 클라우드 한국어 특화 API(ReturnZero 5.91%, CLOVA 7.52%)보다 열세이나, 로컬 엔진 중에서는 최상위권. 짧은 가전 제어 명령(어휘 제한적)에서는 실효 정확도가 벤치마크(강의·회의 등 장문)보다 높게 나오는 것이 일반적.
- **turbo의 한국어 저하:** turbo는 디코더를 32→4층으로 축소(809M 파라미터). OpenAI 모델 카드 기준 비영어권에서 large-v3 대비 1~2% 수준의 정확도 저하가 있으며 저자원 언어일수록 큼. 한국어는 고자원 언어라 저하 폭이 작은 편 — 홈어시스턴트 명령 용도로는 turbo로 충분하다는 것이 커뮤니티 중론.
- **한국어 파인튜닝 모델:** `ghost613/whisper-large-v3-turbo-korean`(zeroth-korean 데이터셋 파인튜닝) 및 CTranslate2 변환본 `ghost613/faster-whisper-large-v3-turbo-korean`이 존재. faster-whisper에서 모델 경로만 바꿔 그대로 사용 가능 → 품질 A/B 테스트 후보.
- 참고: 한국어는 교착어 특성상 **WER보다 CER**로 평가하는 것이 표준 (rtzr 벤치마크 방법론).

### 1.2 RTX 5080 예상 지연 (3~5초 발화)

- 공개 벤치마크 근거:
  - RTX 4090 + faster-whisper turbo INT8: 3초 오디오 청크 인퍼런스 15ms 미만(인코더 청크 기준, 낙관치), per-chunk ~22ms 보고.
  - GTX 1060 + turbo: 약 1초 (Home Assistant 커뮤니티 실측).
  - RTX 4070 + large-v3 INT8: ~12× 실시간.
  - turbo는 large-v3 대비 4~6배 빠르며, "RTX 3090 + turbo가 RTX 5090 + large-v3보다 빠름".
- **RTX 5080(float16) 보수적 추정:** 3~5초 발화 1건 전사(전체 파이프라인 제외, 순수 STT) **약 0.2~0.5초**. large-v3(float16)도 **0.5~1.0초** 수준. 둘 다 "발화 종료 → 텍스트" 체감 지연 목표(1초 이내)에 부합.
- 지연의 지배 요인은 STT 인퍼런스가 아니라 **VAD 발화-종료 판정 대기(end-of-speech silence, 보통 0.5~0.8초)** — VAD 파라미터 튜닝이 더 중요.

### 1.3 스트리밍(partial) 지원 방식

- faster-whisper 자체는 **완결 발화 단위(utterance-level) 전사만 지원, 네이티브 스트리밍 없음.** Whisper는 30초 윈도 기반 full-sequence 모델이기 때문.
- partial이 필요하면 래퍼 계층으로 해결:
  - **whisper_streaming (ufal):** LocalAgreement-n 정책(연속 n회 업데이트에서 일치한 prefix만 확정) + 슬라이딩 윈도 재전사. 지연 약 0.5~0.8초. 논문 기반(ACL 2023 데모).
  - **WhisperLive (Collabora):** faster-whisper 백엔드의 준실시간 WebSocket 서버.
  - **WhisperLiveKit:** 최신 동시통역식 스트리밍 구현 모음.
- **cozy-buddy 권고:** 1~5초 명령 발화에서는 partial의 UX 이득이 작음(발화가 끝나기 전에 명령이 완성되지 않음). **VAD 발화 분할 → 발화 단위 일괄 전사**가 단순·정확·충분. 단, STT provider 인터페이스에는 `on_partial` 콜백을 정의해 두고 초기 구현은 미발화(final만) — 추후 CLOVA gRPC 같은 진짜 스트리밍 provider로 교체 시 활용.

### 1.4 VRAM 점유

| 모델 | float16 | INT8 (5080 불가) |
|---|---|---|
| large-v3 | ~3.0GB 로드 (+인퍼런스 오버헤드 ~20% → 실사용 ~3.5GB) | ~2.9GB |
| large-v3-turbo | **~1.6~2.0GB** | ~1.5GB |

- RTX 5080 16GB에서 turbo(fp16) 사용 시 **LLM에 13GB 이상 잔여** — 7~8B Q4 LLM(+KV캐시) 및 로컬 TTS와 동시 상주 여유 충분.
- large-v3(fp16)를 써도 12GB+ 잔여로 무리 없음. 다만 turbo가 지연·VRAM 모두 유리.

### 1.5 Blackwell(RTX 5080) 호환성 주의 (IMPORTANT)

- CTranslate2 구버전: sm_120에서 INT8 사용 시 `CUBLAS_STATUS_NOT_SUPPORTED` 즉시 크래시 (SubtitleEdit #10180, whisperX #1211 등 다수 보고).
- CTranslate2 4.6.x: **sm120 INT8 지원을 공식적으로 비활성화** (PR #1937) → 크래시 대신 fallback.
- **조치:** `WhisperModel(..., compute_type="float16")` 명시. PyTorch 의존 구성 시 cu128 이상 빌드 필요.

---

## 2. 대안 로컬 엔진

### 2.1 whisper.cpp

- CPU/Metal/CUDA/Vulkan 크로스플랫폼이 강점. **NVIDIA GPU에서는 faster-whisper(CTranslate2)가 더 빠름** — 서버가 NVIDIA 고정인 본 프로젝트에서 채택 이유 없음.
- 의미 있는 시나리오: 서버 없이 태블릿/저사양 기기에서 STT를 돌리는 fallback provider (Android 클라이언트 측 옵션).

### 2.2 sherpa-onnx 스트리밍 zipformer (한국어)

- **한국어 모델 존재:** `sherpa-onnx-streaming-zipformer-korean-2024-06-16` (KsponSpeech 학습, icefall pruned-transducer-stateless7-streaming 변환). 비스트리밍판 `sherpa-onnx-zipformer-korean-2024-06-24`도 있음. ~60MB, 모바일에서 160ms 지연 — 진짜 스트리밍(토큰 단위 partial) 가능.
- **치명 이슈:** GitHub #2886 — 한국어 스트리밍 모델 2종이 **빈 문자열만 반환**하는 미해결 버그 보고(2025~2026, 타 언어는 정상). 모델 export 결함 의심, 유지보수 응답 없음.
- KsponSpeech 단일 데이터셋 학습이라 Whisper 대비 도메인 일반화 열세 예상.
- **판정: 채택 보류.** 초저지연·CPU-only가 필요해질 때 재평가. 어댑터 인터페이스만 열어둠.

### 2.3 NVIDIA Parakeet / Canary

- **구형** `parakeet-1.1b-rnnt-multilingual` (NIM): 25개 언어에 **ko-KR 포함** — 유일한 한국어 지원 경로이나 NIM 컨테이너 중심 배포로 자가호스팅 무게가 큼.
- **최신(2025) Granary 기반** Canary-1b-v2, parakeet-tdt-0.6b-v3: **유럽 25개 언어 전용, 한국어 미지원.**
- **판정: 제외.** 영어 전용이면 최강 후보지만 한국어 우선 요구에 부적합.

### 2.4 SenseVoice (FunASR)

- CJK 특화 비자기회귀 모델. **52× 실시간**의 압도적 속도, 한국어 지원. 단 **한국어 정확도는 Whisper가 우세**(SenseVoice는 중국어/광둥어에서 우세).
- Home Assistant Whisper 애드온이 한/중/일 언어 설정 시 funasr(SenseVoice) 백엔드를 자동 선택할 만큼 검증된 조합 — GPU가 없거나 VRAM이 극도로 부족한 환경의 대체재.
- **판정: 2순위 로컬 교체 후보.** RTX 5080에서는 속도 이점이 무의미(faster-whisper도 충분히 빠름)하고 정확도가 열세.

---

## 3. 클라우드 교체 후보 (provider 어댑터 대상)

| 항목 | CLOVA Speech (NCP) | ReturnZero VITO (RTZR) | Deepgram nova-3 | OpenAI gpt-4o-transcribe |
|---|---|---|---|---|
| 한국어 CER (rtzr 벤치) | 7.52% (2위) | **5.91% (1위)** | ko 지원, nova-3에서 한국어 WER 최대 27% 개선 | 미측정 (99+개 언어 지원) |
| 실시간 스트리밍 | **gRPC 전용** (16kHz/1ch/16bit PCM) | gRPC + WebSocket | WebSocket, **sub-300ms** 지연 | 표준 엔드포인트는 배치 위주, Realtime API 별도 |
| 과금 | 10초당 5원 수준 (부가기능 제외 시) | 시간당 1,000원 종량제(무료 티어 있음) | 스트리밍 ~$0.0077/min | ~$0.006/min (mini는 ~$0.003/min) |
| 특징 | 네이버 한국어 연구 기반 최고 수준 인식률, 국내 리전 | 한국어 벤치 1위, 국내 스타트업 | 다국어·저지연 균형, 개발자 경험 우수 | LLM 후처리 결합 시 문맥 보정 강함 |

- **어댑터 우선순위:** ① CLOVA gRPC(한국어 품질 + 진짜 partial 스트리밍 레퍼런스 구현) ② VITO(WebSocket이라 구현 쉬움, 벤치 1위) ③ Deepgram(해외 이전/다국어 확장 시) ④ OpenAI(이미 LLM으로 쓸 경우 운영 단순화).
- 공통 인터페이스 설계 시 주의: CLOVA는 gRPC 전용이므로 provider 추상화가 전송 프로토콜에 중립적이어야 함 (`start_stream / feed_pcm / on_partial / on_final / close`).

---

## 4. 선택 기준 (짧은 명령 발화 + VRAM 동시 상주)

1. **utterance-level 처리로 충분** — 1~5초 명령은 VAD로 발화 경계를 잡아 일괄 전사하는 편이 스트리밍 재전사보다 정확하고 구현이 단순. partial 스트리밍은 장문 받아쓰기·자막용 요구사항.
2. **체감 지연 예산:** VAD 종료판정(~0.5s) + STT(0.2~0.5s) + LLM 1st token + TTS 1st chunk. STT는 turbo로 충분히 짧아 병목이 아님 → **VAD 튜닝과 LLM/TTS 스트리밍이 실제 승부처.**
3. **VRAM 예산(16GB):** STT는 상시 상주가 유리(cold load 수 초). turbo fp16 ~2GB 고정 점유가 상한선으로 적절. large-v3는 품질 이슈 발생 시에만 승격.
4. **짧은 발화 환각 주의:** Whisper는 무음·잡음 입력에서 환각("시청해주셔서 감사합니다" 류) 발생 → `vad_filter=True` + `no_speech_threshold` + wake word 이후에만 STT 트리거로 방어.
5. **도메인 보정:** `initial_prompt`에 기기명·방 이름 등 도메인 어휘를 주입하면 고유명사 인식률 개선 (faster-whisper 지원).

---

## 5. 최종 권고

- **기본:** `faster-whisper` + `large-v3-turbo`, `compute_type="float16"`(Blackwell 필수), `vad_filter=True`, 발화 단위 전사. VRAM ~2GB, 3~5초 발화 0.2~0.5초.
- **설정 한 줄 교체 후보 (STTProvider 어댑터):**
  1. `faster-whisper:large-v3` — 품질 상향
  2. `faster-whisper:ghost613/faster-whisper-large-v3-turbo-korean` — 한국어 파인튜닝
  3. `clova-speech` (gRPC) — 클라우드 최고 한국어 품질 + partial
  4. `rtzr-vito` (WebSocket) — 한국어 벤치 1위 클라우드
  5. `deepgram:nova-3` / `openai:gpt-4o-transcribe` — 다국어/운영 단순화
  6. `sensevoice` — 저사양 fallback
- **비채택:** sherpa-onnx 한국어 스트리밍(빈 결과 미해결 버그), NVIDIA Parakeet/Canary 최신판(한국어 미지원), whisper.cpp 서버 용도(NVIDIA에서 faster-whisper 열세).

---

## 출처

- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- Whisper turbo 성능/구조: https://whispernotes.app/blog/introducing-whisper-large-v3-turbo , https://convertaudiototext.com/blog/whisper-large-v3-explained
- GPU 지연/RTF: https://gigagpu.com/best-gpu-for-whisper/ , https://gigagpu.com/whisper-large-v3-turbo-speed-accuracy/ , https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026
- VRAM: https://gigagpu.com/whisper-vram-requirements/ , https://vexascribe.com/faster-whisper
- Blackwell INT8 이슈: https://github.com/SubtitleEdit/subtitleedit/issues/10180 , https://github.com/m-bain/whisperX/issues/1211 , https://github.com/OpenNMT/CTranslate2/releases (4.6.x: sm120 INT8 disabled, PR #1937)
- HA 커뮤니티 실측: https://community.home-assistant.io/t/even-faster-whisper-for-local-voice-low-latency-stt/864762
- 스트리밍 래퍼: https://github.com/ufal/whisper_streaming (LocalAgreement) , https://github.com/collabora/WhisperLive , https://github.com/QuentinFuxa/WhisperLiveKit
- 한국어 파인튜닝: https://huggingface.co/ghost613/faster-whisper-large-v3-turbo-korean
- sherpa-onnx 한국어: https://huggingface.co/k2-fsa/sherpa-onnx-streaming-zipformer-korean-2024-06-16 , https://github.com/k2-fsa/sherpa-onnx/issues/2886 (빈 결과 버그)
- NVIDIA: https://build.nvidia.com/nvidia/parakeet-1_1b-rnnt-multilingual-asr/modelcard , https://blogs.nvidia.com/blog/speech-ai-dataset-models/ (Granary=유럽 25개 언어)
- SenseVoice: https://whispernotes.app/blog/sensevoice-fastest-cjk-transcription , https://github.com/home-assistant/addons/blob/master/whisper/DOCS.md
- 한국어 STT 벤치마크(CER): https://github.com/rtzr/Awesome-Korean-Speech-Recognition
- CLOVA Speech: https://api.ncloud-docs.com/docs/ai-application-service-clovaspeech-grpc , https://www.ncloud.com/product/aiService/clovaSpeech
- VITO: https://developers.rtzr.ai/ , https://developers.rtzr.ai/docs/stt-streaming/websocket/
- Deepgram: https://deepgram.com/learn/introducing-nova-3-speech-to-text-api , https://deepgram.com/pricing
- OpenAI: https://developers.openai.com/api/docs/models/gpt-4o-transcribe , https://costgoat.com/pricing/openai-transcription
