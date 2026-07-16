# cozy-buddy 서버측 한국어 TTS 선정 리서치

- 조사일: 2026-07-16
- 전제: 자가호스팅(RTX 5080 16GB / Ryzen 7 7800X3D / 32GB RAM), LAN 내 완결, 한국어 우선,
  홈어시스턴트용 짧은 응답(1~2문장) 위주, **스트리밍(첫 오디오 청크 지연 최소화) 필수**,
  TTS는 provider 인터페이스로 추상화되어 설정 한 줄 교체 가능해야 함.
- VRAM 예산 주의: 같은 GPU에서 LLM + STT(Whisper 계열)와 동거해야 하므로 TTS의 VRAM 점유는 작을수록 좋음.

---

## 1. Piper — 한국어 지원 실태 (결론: 부적합)

| 항목 | 내용 |
|---|---|
| 공식 한국어 보이스 | **없음.** 공식 보이스 목록에 ko 부재. 한국어 지원 요청 이슈/디스커션만 존재 ([#679](https://github.com/rhasspy/piper/issues/679), [#680](https://github.com/rhasspy/piper/discussions/680)) |
| 프로젝트 상태 | 원본 `rhasspy/piper`는 **2025-10 아카이브(개발 중단)**. 후계는 `OHF-Voice/piper1-gpl`(GPL-3.0) |
| 커뮤니티 한국어 모델 | [neurlang/piper-onnx-kss-korean](https://huggingface.co/neurlang/piper-onnx-kss-korean) — KSS 데이터셋 기반 tiny 모델 ([제작기 블로그](https://blog.hashtron.cloud/post/2025-09-28-training-a-a-tiny-piper-tts-model-for-any-language/)). 단일 화자·소형 모델로 품질 한계 뚜렷 |
| 포크 | [piper-plus](https://github.com/ayutaz/piper-plus) (MIT) — 자체 G2P로 KO 포함 8개 언어 지원 주장. 다만 한국어 품질 검증 자료 부족 |

**판정:** Piper는 "한국어 공식 보이스 부재 + 원본 아카이브"로 cozy-buddy 기본 채택 불가.
Home Assistant 기본 스택(Wyoming+Piper)을 그대로 따라가면 한국어에서 막히는 지점이 바로 여기.

---

## 2. 로컬 대안 비교

### 2.1 Supertonic (Supertone) — ★ 기본 채택 후보

- 레포: [supertone-inc/supertonic](https://github.com/supertone-inc/supertonic) / 모델: [HF Supertone/supertonic-3](https://huggingface.co/Supertone/supertonic-3)
- **한국 회사(Supertone, 하이브 계열)가 만든 온디바이스 TTS** — 한국어가 1급 시민. Supertonic 3(2026-05 공식화)는 31개 언어 지원, 한국어 포함.
- 크기/속도: **~99M 파라미터(ONNX)**, RTF **0.005(RTX 4090)** / **0.015(M4 Pro CPU)** — CPU만으로 재생속도의 60배 이상. GPU 불필요, e-리더에서도 RTF 0.3 ([docs](https://supertone-inc.github.io/supertonic-py/)).
- 스트리밍: 네이티브 토큰 스트리밍 API는 없으나 **문장/청크 단위 분할 합성**(한국어 기본 max_chunk_length=120) + RTF가 극단적으로 낮아 **1~2문장 응답 기준 첫 오디오까지 사실상 수십 ms** → 스트리밍 요구를 실질 충족.
- 라이선스: 코드 MIT, **모델 OpenRAIL-M**(상용 포함 사용 허용 + 책임 있는 사용 제한 조항) → 개인 자가호스팅 문제 없음.
- 통합: Python 라이브러리 + **OpenAI Audio Speech API 호환 로컬 HTTP 래퍼** 제공 → provider 어댑터 작성 용이.
- 약점: 보이스 클로닝 없음(제공 보이스 스타일 선택), 감정 표현 폭은 대형 모델 대비 제한.

### 2.2 CosyVoice2 / Fun-CosyVoice3 (Alibaba FunAudioLLM) — ★ 고품질 교체 후보

- 레포: [FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice) / [CosyVoice2-0.5B](https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B) / [Fun-CosyVoice3-0.5B-2512](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512)
- 한국어: 9개 공용어에 KO 포함. 학습 데이터 중 한국어 **약 2.2k시간** ([CosyVoice2 논문](https://funaudiollm.github.io/pdf/CosyVoice_2.pdf)).
- 스트리밍: **텍스트 입력 스트리밍 + 오디오 출력 스트리밍 양방향 지원, 첫 패킷 지연 ~150ms** — 이번 조사 대상 중 유일한 "진짜" 양방향 스트리밍 설계.
- 성능: TensorRT-LLM 가속으로 HF transformers 대비 4배 가속(2025-08). VRAM은 0.5B LLM 기반이라 FP16 기준 수 GB 수준(공식 명시 없음, 16GB급 GPU 배포 사례 다수) — LLM과 동거 시 예산 압박 요인.
- 라이선스: **Apache-2.0** (Fun-CosyVoice3-0.5B-2512, 2025-12 공개).
- 강점: 제로샷 보이스 클로닝, 감정/스타일 지시. 약점: 파이프라인 무겁고(PyTorch 스택) 짧은 응답용으로는 과무장.

### 2.3 GPT-SoVITS — 보이스 클로닝 특화 교체 후보

- 레포: [RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) — **MIT**
- 한국어: 공식 지원(ZH/EN/JA/KO/YUE), 교차언어 추론 가능. 1분 음성으로 few-shot 클로닝.
- 스트리밍: `api_v2.py`에 **streaming_mode** 존재(semantic token 청크 단위, [문서](https://docsmith.aigne.io/discuss/docs/gpt-sovits/en/api-streaming-d125ca)) — 준실시간 가능하나 첫 청크 지연은 Supertonic/CosyVoice보다 큼.
- 하드웨어: 추론 **VRAM 6GB+**, 학습 12GB+.
- 판정: "우리집 전용 목소리"를 원할 때의 옵션. 기본용으로는 지연·운영 복잡도에서 불리.

### 2.4 MeloTTS — CPU 초경량 fallback

- 레포: [myshell-ai/MeloTTS](https://github.com/myshell-ai/MeloTTS) / [MeloTTS-Korean](https://huggingface.co/myshell-ai/MeloTTS-Korean) — **MIT**, CPU 실시간.
- 한국어 모델 존재하나 **단일 화자 + 품질 평범**. 커뮤니티에서 한국어는 톤/스타일 제어가 사실상 안 된다는 보고 ([arca.live](https://arca.live/b/aispeech/152165185)). 2024 이후 업데이트 정체.
- 판정: GPU 죽었을 때 CPU-only 비상 fallback 정도. Supertonic이 CPU에서도 더 빠르고 좋아서 존재 의의 약함.

### 2.5 Kokoro-82M — 한국어 미지원 (탈락)

- [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (Apache-2.0): v1.0 지원 언어는 미/영 영어·일·중·스·프·힌디·이탈리아·브라질포르투갈어 — **[공식 VOICES.md](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)에 한국어 없음**. (일부 서드파티 사이트의 "Korean 지원" 표기는 오정보.)

### 2.6 F5-TTS — 한국어 공식 없음 (탈락)

- [SWivid/F5-TTS](https://github.com/swivid/f5-tts): 코드 MIT이나 기본 모델은 CC-BY-NC 계열 데이터 학습. **공식 한국어 모델/파인튜닝 부재** (HF 파인튜닝 목록에도 KO 부재). 확산 기반이라 스트리밍·지연 특성도 홈허브용으로 불리.

### 2.7 기타

- **MMS-TTS(kor)** (Meta): CC-BY-NC 4.0, 품질 낮음 — 제외.
- **Orpheus-3B(ko Q8)**: Apache-2.0 GGUF, 3B급이라 VRAM 부담 크고 한국어 커뮤니티 검증 부족 — 관찰 대상.
- 참고 큐레이션: [Awesome-Korean-TTS-Local](https://github.com/HeeJayC/Awesome-Korean-TTS-Local-)

### 로컬 후보 요약표

| 모델 | 한국어 품질 | 첫 청크 지연 | 스트리밍 | VRAM/CPU | 라이선스 | 비고 |
|---|---|---|---|---|---|---|
| **Supertonic 3** | 상(한국어 네이티브 개발) | 수십 ms급(RTF 0.005 GPU/0.015 CPU) | 청크 합성(실질 충족) | GPU 불필요, 점유 미미 | MIT+OpenRAIL-M | 기본 채택 |
| **CosyVoice2/3-0.5B** | 상(클로닝·감정) | ~150ms | **양방향 네이티브** | 수 GB(FP16) | Apache-2.0 | 고품질 대안 |
| GPT-SoVITS | 상(클로닝) | 수백 ms~ | api_v2 streaming | 6GB+ | MIT | 커스텀 보이스용 |
| MeloTTS-Korean | 중하 | 빠름 | 없음(짧아서 무의미) | CPU 실시간 | MIT | 비상 fallback |
| Piper(+KSS) | 하(커뮤니티) | 매우 빠름 | 문장 단위 | CPU | MIT/GPL-3.0 | 탈락 |
| Kokoro-82M | **미지원** | - | - | - | Apache-2.0 | 탈락 |
| F5-TTS | **공식 미지원** | 느림 | 부분 | 8GB+ | MIT(코드) | 탈락 |

---

## 3. 클라우드 교체 후보 (TTSProvider 어댑터로 병행)

| 서비스 | 한국어 | 스트리밍/지연 | 가격 | 비고 |
|---|---|---|---|---|
| [OpenAI gpt-4o-mini-tts](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts) | 50+개 언어에 KO 포함(억양은 원어민 대비 아쉽다는 평 존재) | 스트리밍 지원, 첫 청크 ~300–600ms | $0.60/1M 입력토큰 + $12/1M 오디오토큰 ≈ **$0.015/분** | 2025-03 출시, 지시문으로 톤 제어 |
| [Google Chirp 3: HD](https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd) | KO 지원 | 텍스트 스트리밍 입력 + 저지연 실시간 | **$30/1M자**(무료 1M자/월) | GCP 생태계, 안정성 최상 |
| [Typecast API](https://typecast.ai/developers/api) | **한국어 특화(국내 업체)** | 스트리밍, **~200ms** | 1크레딧/자, Lite $9=10만 크레딧 | 한국어 감정 표현 강점 |
| [ElevenLabs Flash v2.5](https://elevenlabs.io/docs/overview/models) | 32개 언어에 KO 포함 | **~75ms**(최저 지연급) | 구독제(로컬 대비 고가) | 지연 벤치마크 기준점 |
| Supertone API / Play | 한국어 최상급 | Supertonic 3 기반 | 상용 API | 로컬 Supertonic과 같은 계열이라 어댑터 재사용 여지 |

클라우드는 "로컬 우선" 원칙상 기본이 아니라 **품질 비교·장애 대비용 교체 슬롯**. 인터페이스만 맞추면 됨.

---

## 4. 최종 결론 (홈어시스턴트: 짧은 응답 1~2문장, 자연스러움×지연 균형)

### 기본 채택: **Supertonic 3** (로컬, ONNX)

근거:
1. **한국어 품질** — 한국 회사가 한국어를 핵심 타깃으로 개발, 31개 언어 중에서도 KO가 원년 멤버(공개 데모 기준 로컬 오픈 모델 중 한국어 자연스러움 최상위권).
2. **지연** — RTF 0.005(GPU)/0.015(CPU)로 1~2문장은 사실상 즉시 합성. 네이티브 스트리밍이 없어도 첫 오디오 지연 요건을 가장 잘 충족. LLM 토큰 스트림을 문장 단위로 끊어 넘기는 파이프라인(문장별 합성→즉시 재생)과 궁합 최적.
3. **자원** — ~99M ONNX라 VRAM 점유가 사실상 0에 수렴 → RTX 5080 16GB를 LLM+STT에 온전히 배정 가능. GPU 장애 시 CPU로도 실시간.
4. **라이선스/통합** — 코드 MIT, 모델 OpenRAIL-M(자가호스팅 무방). OpenAI 호환 HTTP 래퍼로 어댑터 구현 반나절 거리.

### 교체 후보 (설정 한 줄 스왑)

- **1순위: CosyVoice2/Fun-CosyVoice3-0.5B** — 감정 표현·보이스 클로닝·양방향 스트리밍(~150ms)이 필요해지면. Apache-2.0. VRAM 수 GB 각오.
- **2순위(클라우드): Typecast API** — 한국어 감정 표현 최상급이 필요할 때, ~200ms 스트리밍.
- **3순위(클라우드): OpenAI gpt-4o-mini-tts** — LLM을 이미 OpenAI로 쓸 경우 운영 단순화, $0.015/분.
- **특수: GPT-SoVITS** — 가족 목소리 클로닝 등 커스텀 보이스 요구 시.

### 아키텍처 반영 (provider 추상화)

```
TTSProvider (인터페이스)
  async def synthesize_stream(text: str, voice: str) -> AsyncIterator[bytes]
  구현체: SupertonicProvider(기본) | CosyVoiceProvider | TypecastProvider
        | OpenAITTSProvider | GoogleTTSProvider | MeloTTSProvider(CPU fallback)
설정: tts.provider = "supertonic"  # 한 줄 교체
파이프라인: LLM 토큰 스트림 → 문장 분리기 → 문장 단위 TTS → 오디오 청크 스트리밍 재생
  (Supertonic처럼 비스트리밍이라도 문장 단위 파이프라이닝으로 체감 지연 최소화)
```

### 리스크 메모

- Supertonic 모델의 OpenRAIL-M은 사용 제한 조항이 있는 라이선스 — 개인 자가호스팅에는 문제 없으나, 향후 배포/상용화 시 조항 재검토 필요.
- Piper 생태계(HA 표준)는 한국어에서 사실상 죽은 길 — HA 호환이 필요하면 Wyoming 프로토콜 어댑터를 자체 TTS 서버 앞에 씌우는 편이 낫다.
- Kokoro "한국어 지원" 표기는 서드파티 사이트발 오정보이므로 재검증 없이 채택하지 말 것.

---

## 출처

- Piper KO 요청: https://github.com/rhasspy/piper/issues/679 , https://github.com/rhasspy/piper/discussions/680
- Piper KSS 커뮤니티 모델: https://huggingface.co/neurlang/piper-onnx-kss-korean , https://blog.hashtron.cloud/post/2025-09-28-training-a-a-tiny-piper-tts-model-for-any-language/
- piper-plus: https://github.com/ayutaz/piper-plus
- Supertonic: https://github.com/supertone-inc/supertonic , https://huggingface.co/Supertone/supertonic-3 , https://supertone-inc.github.io/supertonic-py/
- CosyVoice: https://github.com/FunAudioLLM/CosyVoice , https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B , https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512 , https://funaudiollm.github.io/pdf/CosyVoice_2.pdf
- GPT-SoVITS: https://github.com/RVC-Boss/GPT-SoVITS , https://docsmith.aigne.io/discuss/docs/gpt-sovits/en/api-streaming-d125ca
- MeloTTS: https://github.com/myshell-ai/MeloTTS , https://huggingface.co/myshell-ai/MeloTTS-Korean , https://arca.live/b/aispeech/152165185
- Kokoro: https://huggingface.co/hexgrad/Kokoro-82M , https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
- F5-TTS: https://github.com/swivid/f5-tts
- 한국어 로컬 TTS 목록: https://github.com/HeeJayC/Awesome-Korean-TTS-Local-
- OpenAI TTS: https://developers.openai.com/api/docs/models/gpt-4o-mini-tts , https://community.openai.com/t/new-tts-api-pricing-and-gotchas/1150616
- Google Chirp 3 HD: https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd , https://cloud.google.com/text-to-speech/pricing
- Typecast: https://typecast.ai/developers/api , https://typecast.ai/pricing
- ElevenLabs Flash v2.5: https://elevenlabs.io/docs/overview/models
