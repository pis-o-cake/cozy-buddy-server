# LLM 서빙 스택 조사 — cozy-buddy (RTX 5080 16GB, 2026-07-16)

> 전제: STT/TTS와 VRAM 공유(LLM 가용 예산 약 10~12GB), 로컬 우선(LAN 완결), 한국어 우선,
> 워크로드 = "짧은 IoT 툴콜 다수 + 가끔 긴 대화", 단일~소수 동시 사용자.

---

## 0. 결론 요약 (기본 채택 + 교체 후보)

| 항목 | 기본 채택 | 교체/폴백 후보 |
|---|---|---|
| 서빙 엔진 | **llama.cpp `llama-server`** (Windows 네이티브, OpenAI 호환) | vLLM(WSL2, 동시성↑ 필요 시) / Ollama(간편 프로필) |
| 메인 모델 | **Qwen3.5-9B-Instruct GGUF Q4_K_M** (~6GB, Apache 2.0) | Qwen3-8B AWQ, **Kanana-2-30B-A3B-Instruct**(한국어 특화, MoE CPU 오프로드) |
| 경량(의도분류/라우팅) | **Qwen3.5-4B-Instruct Q4** (~3GB) | Midm 2.0 Mini(2.3B), EXAONE 4.0-1.2B(라이선스 주의) |
| 클라우드 폴백 | Claude / Gemini / GPT (provider 어댑터) | — |
| 공통 계약 | **OpenAI-compatible Chat Completions(스트리밍+툴콜+json_schema)** | 자체 `LLMProvider` 인터페이스로 랩핑 |

- **Ollama 래핑 코드는 "OpenAI 호환 제네릭 어댑터"로 일반화**하고, 기본 백엔드를 llama.cpp server로 교체 권장(§3 근거).
- TTFT 목표(짧은 툴콜 턴 ≤ 0.5초): **프리픽스(프롬프트) 캐싱 + 모델 상주 + 툴 스키마 최소화** 전제 하에 달성 가능(§5).

---

## 1. 서빙 엔진 비교 (Windows/WSL2 + Blackwell RTX 5080)

### 1.1 지원 현황 매트릭스

| 엔진 | Windows 네이티브 | WSL2 | Blackwell(sm_120) | 스트리밍+툴콜 | 구조화 출력 | 비고 |
|---|---|---|---|---|---|---|
| **llama.cpp (llama-server)** | O (공식 CUDA 바이너리) | O | O (CC 12.0 인식, 최적화는 `-DGGML_CUDA_ARCHITECTURES=120` 빌드 권장) | O (`--jinja` 기반 OpenAI 스타일 함수콜, 스트리밍 지원) | O (GBNF/json_schema) | 단일 사용자 성능 = Ollama 이상, VRAM 세밀 제어(`--n-gpu-layers`, `--override-tensor`) |
| **Ollama** | O | O | O (RTX 5080 공식 지원 목록, CC 12.0 자동 감지) | 네이티브 `/api/chat`은 2025-05부터 지원. **OpenAI 호환 `/v1`은 스트리밍 시 tool_calls 유실 이슈 보고** | O (`format`/`response_format`) | 텍스트 추론 안정, 비전 추론 CUDA 크래시 이슈(#14446), AMD iGPU 공존 시 CPU 폴백 버그(#11849) |
| **vLLM** | X (WSL2/Docker 필수) | O (WSL2 2.7.0에서 sm_120 CUDA graph 동작 확인, CUDA 12.8+ 필요) | O | O (`--enable-auto-tool-choice --tool-call-parser <hermes/qwen3...>`; 일부 파서 스트리밍 파싱 버그 이력 #31871) | O (xgrammar FSM, strict tool schema 강제) | PagedAttention+연속 배칭, 동시 10+ 사용자에서 Ollama 대비 10~20x. **`--gpu-memory-utilization` 선점 할당이 STT/TTS VRAM 공유와 충돌** — 0.6~0.7로 제한 필요 |
| **SGLang** | X (Linux 전용 커널, WSL2/Docker만) | O | O | O (RadixAttention 프리픽스 캐시 — 반복 툴 스키마에 유리, 구조화/에이전트 특화) | O | 구조화 출력·에이전트 루프 지연 최저. 단, Windows 네이티브 불가 + 운영 복잡도 높음 |
| (참고) TGI | — | — | — | — | — | 2026-03 리포 아카이브, 유지보수 모드 → 신규 채택 배제 |

### 1.2 이 프로젝트 기준 판단

- **단일 사용자 + STT/TTS와 VRAM 공유 + Windows 서버**라는 제약에서:
  - **llama.cpp server가 최적**: 네이티브 Windows 동작, GPU 레이어 단위 VRAM 제어, MoE 전문가 CPU 오프로드(`--override-tensor "experts=CPU"`), 프롬프트 캐시(`--cache-reuse`), OpenAI 호환 API.
  - vLLM은 KV 캐시를 선점 할당하는 구조라 VRAM 공유 시나리오에 불리. 동시 사용자 급증(가족 다중 세션+Flutter 원격) 시에만 WSL2로 승격 검토.
  - SGLang은 툴콜/구조화 특화 장점이 있으나 Windows 네이티브 불가 + 운영 비용 대비 이득이 단일 사용자에선 작음 → 관찰 후보.
- Home Assistant 커뮤니티 실사용 보고: Qwen3.5 툴콜이 **Ollama에서 실패 → llama.cpp로 전환 후 정상 동작** 사례 — "서빙 프레임워크가 툴콜 신뢰도를 좌우"함을 시사.

---

## 2. 모델: 16GB VRAM(실가용 10~12GB), 한국어 + 툴콜 신뢰도

### 2.1 VRAM 예산 (STT/TTS 공유 전제)

| 구성요소 | 예상 VRAM |
|---|---|
| STT (faster-whisper large-v3-turbo, int8_float16) | ~1.5–3GB |
| TTS (한국어 신경망 TTS 1종 상주) | ~1–2GB |
| WakeWord/VAD (openWakeWord/Silero → CPU) | 0 |
| **LLM 가용 예산** | **~10–12GB** (가중치 + KV 캐시) |

→ **8–9B급 Q4/AWQ(가중치 ~5–6GB) + KV 16–32K가 안전권**. 14B AWQ(~9.5GB)는 한계선. 32B 밀집 모델은 불가.

### 2.2 후보 모델 평가

| 모델 | 크기/양자화 | 한국어 | 툴콜 | 라이선스 | 판정 |
|---|---|---|---|---|---|
| **Qwen3.5-9B-Instruct** (2026-03) | Q4_K_M ~6GB | 상 (Qwen3 대비 개선) | 상 (2507계보부터 툴콜 강화, `qwen3` 파서) | **Apache 2.0** | **기본 채택** |
| Qwen3-8B / Qwen3-14B | AWQ ~6GB / ~9.5GB | 상 | 상 (GPTQ는 이슈 → AWQ 권장) | Apache 2.0 | 안정 검증판(차선) |
| **Kanana-2-30B-A3B-Instruct** (Kakao) | MoE Q4 ~18GB → **전문가 CPU 오프로드**(활성 3B만 GPU) | **최상 (한국어 1위권)** | 상 (에이전틱/툴콜 강화가 릴리스 목적) | **Apache 2.0** | **한국어 특화 대안** — 32GB RAM에서 하이브리드 구동 가능, 속도 실측 필요 |
| Qwen3.5-35B-A3B | MoE UD-Q3_K_M ~16.6GB | 상 | 상 | Apache 2.0 | 품질 상한 후보. 16GB 단독은 빠듯 → CPU 오프로드 전제 |
| EXAONE 4.0-32B | Q4 ~18GB+ | 최상 (KMMLU 강세) | 상 (vLLM hermes 파서 공식 지원) | **NC (연구/교육 한정, 상용 별도계약)** | 라이선스+크기로 배제. 1.2B는 대화용으론 과소 |
| HyperCLOVA X SEED (8B Omni / 14B Think) | ~6 / ~9GB | 최상 | 중~상 (chat template에 tool_list 지원) | 자체 라이선스(조건 확인 필요) | 관찰 후보 — GGUF/서빙 생태계 성숙도 확인 후 |
| A.X 4.0-7B (SKT) / Midm 2.0 (KT 11.5B/2.3B) | ~5 / ~7GB | 상 | 중 | 오픈(상용 허용) | 한국어 보조 후보. 툴콜 실측 데이터 부족 |
| gemma-3 (12B/27B) | ~8 / 초과 | 중상 | **하 — Ollama 함수콜 태그 미지원(#9680), 코드블록 폴백 등 파싱 불안정** | Gemma 라이선스 | **배제** (툴콜 신뢰도가 제1 요건) |
| Llama 3.x/4 | 8B ~6GB | 중 (한국어 약세) | 중상 | Llama 라이선스 | 한국어 우선 요건에서 열위 → 배제 |

### 2.3 권장 조합

- **기본**: `Qwen3.5-9B-Instruct` GGUF **Q4_K_M**(품질 우선 시 Q5/Q6) — 툴콜+한국어+라이선스+VRAM 4박자.
- **한국어 품질 최우선 실험**: `Kanana-2-30B-A3B-Instruct` Q4 + `--override-tensor "experts=CPU"` (활성 3B라 하이브리드에서도 실용 속도 기대).
- **경량 슬롯**(웨이크 직후 의도분류, 단순 on/off 툴콜): `Qwen3.5-4B-Instruct` Q4 (~3GB) — 상시 상주시켜 TTFT 최소화하는 2-모델 구성도 가능.

---

## 3. 기존 Ollama 래핑: 유지 vs 교체

**판단: "교체하되 버리지 않는다" — 공통 계약을 OpenAI 호환 API로 일반화, 기본 백엔드는 llama.cpp server, Ollama는 어댑터 하나로 강등.**

교체 근거:
1. **OpenAI 호환 레이어(`/v1`)의 스트리밍+툴콜 유실 버그** — 스트리밍 응답이 `finish_reason: "stop"` + 빈 content로 tool_calls를 드랍하는 사례 보고. 네이티브 `/api/chat`는 정상이지만, 그러면 Ollama 전용 API에 락인됨(추상화 목표와 상충).
2. **실사용 신뢰도**: HA 커뮤니티에서 동일 모델(Qwen3.5) 툴콜이 Ollama에서 실패, llama.cpp에서 정상 — 파서/템플릿 계층 문제.
3. **오버헤드/제어권**: 단일 사용자 처리량 10~30% 오버헤드, 자동 GPU 스케줄링·keep_alive 언로드 등 VRAM 공유 환경에서 제어 곤란.
4. 프로젝트 요건이 이미 "설정 한 줄 교체"이므로, Ollama 고유 API에 맞춘 래퍼는 추상화 방향이 반대.

유지 가치: 설치/모델 관리 편의, RTX 5080 공식 지원 → **개발·간편 설치 프로필용 어댑터로 존치**.

---

## 4. 하이브리드 전략 + Provider 인터페이스

### 4.1 라우팅 패턴 (로컬 기본 + 클라우드 선택/폴백)

- **계층**: `LLMRouter`(정책) → `LLMProvider`(어댑터: llamacpp / ollama / openai / anthropic / gemini).
- **라우팅 축 3가지** (LiteLLM/하이브리드 아키텍처 가이드의 공통 패턴):
  1. **작업 복잡도**: IoT 툴콜·짧은 질의 → 로컬 / 긴 창작·복잡 추론 → 클라우드(옵트인).
  2. **민감도**: 집안 상태·개인 데이터 포함 요청은 **fail-closed로 로컬 고정**.
  3. **가용성 폴백**: 로컬 타임아웃/헬스체크 실패 → 클라우드(설정으로 on/off), 재시도·쿨다운 포함.
- 구현: 자체 경량 라우터 권장(홈서버에 LiteLLM Proxy 상주는 과잉). 단, 설정 스키마는 LiteLLM의 model alias + fallback chain 개념을 차용.

### 4.2 `LLMProvider` 인터페이스에 반드시 담을 것

```python
class LLMProvider(Protocol):
    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None,          # 툴콜 (parallel tool calls 포함)
        response_format: JsonSchema | None,      # 구조화 출력 (json_schema)
        options: GenOptions,                     # temperature, max_tokens, stop, ...
    ) -> AsyncIterator[ChatDelta]: ...           # text delta | tool_call delta | usage | done

    async def health(self) -> ProviderHealth     # 라우터 폴백 판단용
    def capabilities(self) -> Capabilities       # tools/json_schema/vision/reasoning 지원 플래그
```

- **ChatDelta는 3종 이벤트 통합**: 텍스트 조각 / tool_call 조각(id·name·arguments 누적) / 종료(finish_reason, usage). 스트리밍 중 툴콜이 1급 시민이어야 함(로컬 엔진별 파싱 편차를 어댑터가 흡수).
- **capabilities 플래그**: 라우터가 "이 모델은 json_schema 미지원 → 프롬프트 기반 폴백" 같은 결정을 하도록.
- **reasoning(thinking) 분리**: Qwen3/EXAONE 하이브리드 추론 모델은 reasoning 토큰을 별도 채널로(음성으로 읽으면 안 됨).
- **취소(cancellation)**: 웨이크워드 재감지·사용자 인터럽트 시 스트림 즉시 중단 — 음성 UX 필수.
- **프리픽스 캐시 힌트**: system prompt+툴 스키마를 안정된 접두부로 유지하는 규약(캐시 적중률 = TTFT 좌우).
- 클라우드 어댑터는 각 벤더 네이티브 SDK 사용(툴콜 포맷 상호 변환은 어댑터 책임), 로컬은 OpenAI 호환 엔드포인트 공통.

---

## 5. TTFT 목표 달성 가능성 (홈어시스턴트 워크로드)

- 업계 기준치: 음성 왕복 체감 한계 총 1~2초(데스크톱 GPU), **LLM TTFT 설계 목표 ~500ms(이상적 150–250ms)**, STT 0.2–0.5s, TTS 첫 오디오 0.1–0.3s.
- RTX 5080(GDDR7 ~960GB/s)에서 8–9B Q4 기준:
  - **디코드**: 이론 상한 ~190 tok/s, 실측 80–120 tok/s대 — 짧은 툴콜 응답(≤50토큰)은 0.5초 내.
  - **프리필**: 시스템 프롬프트+툴 스키마 2–4K 토큰을 매턴 재처리하면 TTFT 0.3–1s로 악화 →
    **프리픽스 캐싱이 사실상 필수** (llama.cpp `--cache-reuse` / vLLM APC / SGLang RadixAttention).
    캐시 적중 시 신규 사용자 발화(수십 토큰)만 프리필 → **TTFT 50–200ms 달성 가능**.
- 달성 조건 체크리스트:
  1. 모델 상시 상주(언로드 금지 — Ollama keep_alive=-1 상당).
  2. 툴 스키마 다이어트(15–22개 이상이면 소형 모델이 코드블록 폴백 등 오작동 보고 — 도메인별 서브셋 노출).
  3. 문장 단위 스트리밍 TTS 파이프라이닝(첫 문장 완성 즉시 발화).
  4. 경량 모델 우선 응답 + 필요 시 상위 모델 이관(병렬 SLM+LLM 패턴).
- **결론: 짧은 툴콜 다수 워크로드에서 LLM TTFT ≤ 0.5s, 명령→발화 시작 ≤ 1.5s는 현실적 목표.** 긴 대화 턴은 스트리밍으로 체감 지연 흡수.

---

## 6. 최종 권고

1. **서빙**: llama.cpp `llama-server`(Windows 네이티브, `--jinja` 툴콜, `--cache-reuse`, sm_120 빌드) 기본. 동시성 요구 증가 시 vLLM(WSL2, `--gpu-memory-utilization 0.6~0.7`, `--tool-call-parser qwen3`)로 승격 — 어댑터 교체만으로 가능해야 함.
2. **모델**: Qwen3.5-9B-Instruct Q4_K_M 기본 + Qwen3.5-4B 경량 슬롯. 한국어 체감 품질 비교로 Kanana-2-30B-A3B(전문가 CPU 오프로드) A/B 테스트.
3. **Ollama**: 기본 백엔드에서 제외하되 어댑터로 존치(개발 편의 프로필).
4. **하이브리드**: 민감도 fail-closed 로컬 고정 + 복잡도/가용성 기반 클라우드 폴백(옵트인). 인터페이스에 스트리밍 툴콜 델타·json_schema·capabilities·취소·reasoning 분리 포함.
5. **검증 항목(구현 단계)**: (a) llama.cpp 최신 릴리스의 스트리밍+툴콜 동시 동작 버전 확인, (b) Kanana-2 GGUF 툴콜 템플릿 호환성, (c) 프리픽스 캐시 적중 시 실측 TTFT.

---

## 출처

- 서빙 엔진 비교: [TensorFoundry — LLM Inference Servers Compared](https://tensorfoundry.io/blog/llm-inference-servers-compared), [VRLA Tech — 엔진 비교 2026](https://vrlatech.com/llm-inference-engine-comparison-2026/), [Sesame Disk — 로컬 추론 엔진 2026](https://sesamedisk.com/llamacpp-vs-vllm-vs-sglang-vs-ollama-2026/), [InsiderLLM — llama.cpp vs Ollama vs vLLM](https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/), [d-central — 로컬 추론 서버 비교](https://d-central.tech/ollama-vs-vllm-vs-llama-cpp/)
- Blackwell/RTX 5080: [vLLM #37242 — sm_120 + WSL2 2.7.0 CUDA graphs](https://github.com/vllm-project/vllm/issues/37242), [vLLM #14452 — RTX 5080/5090 구동 가이드](https://github.com/vllm-project/vllm/issues/14452), [Ollama GPU 지원 문서](https://docs.ollama.com/gpu), [Ollama #14446 — 5080 비전 추론 크래시](https://github.com/ollama/ollama/issues/14446), [Ollama #11849 — AMD iGPU 공존 CPU 폴백](https://github.com/ollama/ollama/issues/11849), [LLamaSharp #1338 — sm_120 빌드](https://github.com/SciSharp/LLamaSharp/issues/1338)
- 툴콜/스트리밍 API: [vLLM Tool Calling 문서](https://docs.vllm.ai/en/latest/features/tool_calling/), [vLLM #31871 — hermes 파서 스트리밍 버그](https://github.com/vllm-project/vllm/issues/31871), [llama.cpp function-calling.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md), [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md), [Ollama — Streaming with tool calling](https://ollama.com/blog/streaming-tool), [OpenClaw #11828 — Ollama /v1 스트리밍 툴콜 유실](https://github.com/openclaw/openclaw/issues/11828), [SGLang Windows 논의 #4095](https://github.com/sgl-project/sglang/discussions/4095)
- 모델: [Qwen3.5 가이드(2026, 릴리스 타임라인/사이즈)](https://codersera.com/blog/qwen-3-5-complete-guide-2026/), [unsloth Qwen3.5-35B-A3B-GGUF](https://huggingface.co/unsloth/Qwen3.5-35B-A3B-GGUF), [Unsloth — Qwen3.5 로컬 구동 문서](https://unsloth.ai/docs/models/qwen3.5), [QwenLM/Qwen3](https://github.com/QwenLM/Qwen3), [Qwen3-14B-AWQ](https://huggingface.co/Qwen/Qwen3-14B-AWQ), [Qwen3 양자화 선택 가이드](https://tomodahinata.com/en/blog/qwen3-quantization-awq-gptq-fp8-gguf-comparison-guide), [LG EXAONE-4.0 리포](https://github.com/LG-AI-EXAONE/EXAONE-4.0), [EXAONE-4.0-32B (라이선스 1.2-NC)](https://huggingface.co/LGAI-EXAONE/EXAONE-4.0-32B), [kakaocorp/kanana-2-30b-a3b-instruct (Apache 2.0)](https://huggingface.co/kakaocorp/kanana-2-30b-a3b-instruct), [naver-hyperclovax 조직](https://huggingface.co/naver-hyperclovax), [HyperCLOVAX-SEED-Omni-8B](https://huggingface.co/naver-hyperclovax/HyperCLOVAX-SEED-Omni-8B), [SKT/KT 오픈소스 공개 보도](https://www.etnews.com/20250703000032), [Ollama gemma3 함수콜 이슈 #9680](https://github.com/ollama/ollama/issues/9680)
- 실사용/지연: [HA 커뮤니티 — Qwen3.5 툴콜(Ollama→llama.cpp)](https://community.home-assistant.io/t/assist-qwen3-5-35b-a3b-tool-calling/991434), [Local Voice Assistant 2026 (지연 분해)](https://www.promptquorum.com/power-local-llm/build-local-voice-assistant-2026), [Prodinit — Voice AI 지연 허용범위](https://prodinit.com/blog/production-voice-ai-agents-latency-architecture), [WebRTC.ventures — 병렬 SLM+LLM 패턴](https://webrtc.ventures/2025/06/reducing-voice-agent-latency-with-parallel-slms-and-llms/)
- 하이브리드 라우팅: [SitePoint — Hybrid Cloud-Local LLM 아키텍처(2026)](https://www.sitepoint.com/hybrid-cloudlocal-llm-the-complete-architecture-guide-2026/), [LiteLLM Router 문서](https://docs.litellm.ai/docs/routing), [LiteLLM Fallbacks](https://docs.litellm.ai/docs/proxy/reliability)
