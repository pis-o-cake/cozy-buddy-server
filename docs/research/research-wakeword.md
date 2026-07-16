# cozy-buddy 웨이크워드 엔진 조사 — Android 태블릿 온디바이스

- 조사일: 2026-07-16
- 대상: Android 태블릿 허브 클라이언트, 한국어 커스텀 호출어("코지야" 류), 로컬 우선(LAN 완결), provider/adapter 추상화 전제
- 결론 요약: **기본 채택 = Picovoice Porcupine**, 교체 1순위 = openWakeWord(자체 온디바이스 통합), 폴백 = Vosk grammar mode, 관찰 = LiveKit WakeWord

---

## ⚠️ 부록 (v3.1, 2026-07-16) — 결론 뒤집힘: 웨이크워드 "jarvis" 확정으로 openWakeWord 기본 복귀

본 조사의 채택 논리는 "**한국어 커스텀 호출어를 지금 당장**"이 제1 요건이라는 전제였다. 이후 사용자가 호출어를 **"jarvis"(영어)로 확정**하고 Porcupine Free 티어(MAU 3·다중 계정 차단)를 실사용 부적합으로 판정하면서 전제가 소멸 — 설계서 v3.1은 아래 근거로 **openWakeWord를 기본으로 복귀**시켰다.

1. **openWakeWord 공식 사전학습 `hey_jarvis` 모델 존재** — ONNX/TFLite, ~20만 합성 클립 학습, 릴리스에 포함. "jarvis" 단독 호출도 동작하나 미탐률 증가 명시(원문: "other similar phrases such as just 'jarvis' may also work, but likely with higher false-reject rates"). [모델 카드](https://github.com/dscripka/openWakeWord/blob/main/docs/models/hey_jarvis.md)
2. **LiveKit wakeword의 ONNX 출력이 openWakeWord 추론 파이프라인과 완전 호환** — 커맨드 한 줄로 합성 데이터 생성→증강→학습→ONNX 내보내기. 한국식 발음 증강·"jarvis" 단독 모델을 **무제한 무료**로 재학습 가능. 본 조사 시점엔 "관찰"이었으나 커스텀 학습 경로로 승격. [블로그](https://livekit.com/blog/livekit-wakeword) · [export 문서](https://github.com/livekit/livekit-wakeword/blob/main/docs/export-and-inference.md)
3. **Android 통합 레퍼런스 추가 확인** — [Re-MENTIA/openwakeword-android-kt](https://github.com/Re-MENTIA/openwakeword-android-kt) (Kotlin, Apache-2.0, ONNX Runtime, Flow API). 여전히 커뮤니티 수준이므로 §2.2의 실기기 검증 필수 경고는 유효.
4. **폴백 엔진 없음으로 확정** — Vosk는 성능 부적합(사용자 판정)으로 제외. 초기화 실패 시 오류 배너 + 백오프 재시도, 터치/텍스트 경로만 유지. Porcupine은 상용 슬롯으로 강등(내장 "Jarvis" 키워드가 있어 어댑터 구현은 유효).

---

## 1. 결론 및 권고

| 순위 | 엔진 | 역할 | 핵심 근거 |
|---|---|---|---|
| 채택 | **Porcupine** | 기본 프로바이더 | 한국어 공식 지원 + Console에서 커스텀 워드 즉시 생성(.ppn), Android SDK 최고 성숙도, 1MB 모델 / 초저부하, 97%+ 정확도 벤치마크 |
| 교체 1순위 | **openWakeWord** | 완전 오픈소스 대체재 | ONNX/TFLite로 Android 직접 통합 가능. 단 한국어는 비공식 학습 경로(openwakeword.com 등) 필요, 공식 Android SDK 없음 |
| 폴백 | **Vosk (grammar mode)** | 라이선스 제약 0의 완전 로컬 폴백 | 한국어 모델 존재, Android 실전 사례(일본어) 검증됨. CPU/RAM 부담 최대 |
| 관찰 | **LiveKit WakeWord** | 2026 신규, 잠재적 차세대 | openWakeWord 대비 오탐 ~100x 감소 주장, Apache-2.0, 30+개 언어 합성 학습. Android 미지원(v0.1.0, 2026-02) |
| 제외 | microWakeWord, sherpa-onnx KWS | — | 아래 3장 참조 |

**채택 논리:**
- 제1 요건은 "한국어 커스텀 호출어를 지금 당장, 낮은 오탐으로" — 이를 상용 수준으로 충족하는 것은 Porcupine이 유일.
- Porcupine의 약점(AccessKey 온라인 검증, free tier 제약)은 개인 프로젝트 + 태블릿 1~2대 규모에서는 실질 문제 없음. 단 "로컬 우선" 철학과의 충돌 지점이므로 **추상화 인터페이스를 처음부터 강제**하고, openWakeWord 어댑터를 2번째로 구현해 락인을 차단.
- "코지야"는 3음절로 오탐 경계선. 4음절 이상("헤이 코지", "코지야아" 류 변형) 병행 학습·비교 권장 — Porcupine Console에서 몇 초 만에 재생성 가능하므로 실험 비용이 거의 0.

---

## 2. 엔진별 상세

### 2.1 Picovoice Porcupine

**한국어/커스텀 워드**
- 지원 언어에 **한국어 공식 포함** (EN/FR/DE/IT/JA/**KO**/ZH/PT/ES). Android SDK도 한국어 지원 명시. [제품 페이지](https://picovoice.ai/products/voice/wake-word/), [Android Quick Start](https://picovoice.ai/docs/quick-start/porcupine-android/)
- 커스텀 워드: [Picovoice Console](https://picovoice.ai/blog/console-tutorial-custom-wake-word/)에서 한글 텍스트 입력 → 수 초 내 모델 학습 → `.ppn` 파일 다운로드 → Android assets에 포함. 음성 샘플 수집 불필요.

**라이선스/무료 티어 (2025~2026 기준)**
- Free 플랜: 개인·비상업 용도. **월 활성 사용자(MAU) 3** 수준(기기/앱 인스턴스 단위, 30일 리셋), **커스텀 워드 학습 월 3회** 제한. [Picovoice FAQ](https://picovoice.ai/docs/faq/general/), [Hackster 보도](https://www.hackster.io/news/picovoice-launches-completely-free-usage-tier-for-offline-voice-recognition-for-up-to-three-users-e1eafbc97bb0)
- 유료: Foundation 플랜 $6,000/년(Porcupine 100 users/월 포함, 5년 미만·20인 이하 스타트업 한정). 일반 상용은 세일즈 문의. [Pricing](https://picovoice.ai/pricing/)
- **중요 제약:** 추론은 100% 온디바이스지만, **엔진 초기화 시 AccessKey를 라이선스 서버와 온라인 검증**(사용량 집계 목적). 완전 오프라인 환경에서는 초기화 실패 가능. [FAQ](https://picovoice.ai/docs/faq/general/), [HN 논의](https://news.ycombinator.com/item?id=33964527)
- SDK 코드 자체는 Apache-2.0([GitHub](https://github.com/picovoice/porcupine))이나 모델·엔진 바이너리는 프로프라이어터리.

**Android SDK 성숙도**
- Maven Central 배포, foreground service 데모, 버전 3.x까지 장기 유지보수. 조사한 엔진 중 유일하게 "공식 Android SDK + 문서 + 데모"가 완비. [Android API 문서](https://picovoice.ai/docs/api/porcupine-android/)

**성능/부하**
- 표준 모델 ~1MB, RPi3(Cortex-A53) 1코어의 3.8% CPU → 현대 Android 태블릿에서는 ~1% 미만 수준. [v1.8 Feature Tour](https://picovoice.ai/blog/porcupine-wake-word-engine-v1-8-feature-tour/)
- 벤치마크: 10dB SNR에서 **97.1% 검출률 @ 오탐 1회/10시간**. 자사 비교에서 경쟁 엔진 대비 2.5x 정확, 2.6x 빠름 주장(자사 벤치이므로 감안). [벤치마크](https://picovoice.ai/products/voice/wake-word/), [Medium 벤치 해설](https://medium.com/@alirezakenarsarianhari/yet-another-wake-word-detection-engine-a2486d36d8d4)
- 입력: 16kHz mono PCM, **프레임 512 샘플 고정**, `sensitivity` 0~1 파라미터로 오탐/미탐 트레이드오프 조정.

### 2.2 openWakeWord

**Android 실전 구동**
- 공식 Android SDK 없음. 모델이 ONNX/TFLite이므로 onnxruntime-android 또는 TFLite로 직접 구동 가능하나, melspectrogram → embedding → classifier 3단 파이프라인을 앱에서 재현해야 함. [GitHub](https://github.com/dscripka/openWakeWord)
- 커뮤니티 포트 [Willy8m/openWakeWord-Android](https://github.com/Willy8m/openWakeWord-Android)(Kotlin+C++, TFLite/ONNX 겸용) 존재하나 12 stars, 릴리스 없음 — **실험 수준, 참고용**. Android TFLite에서 tensor allocation 크래시 이슈 리포트도 있음([Issue #223](https://github.com/dscripka/openWakeWord/issues/223)).

**한국어/커스텀 워드 학습**
- **본가(dscripka)는 공식적으로 영어 전용** — 학습 데이터 생성용 TTS가 영어 기반이기 때문. [README](https://github.com/dscripka/openWakeWord), [HA 공식 입장](https://www.home-assistant.io/voice_control/about_wake_word/)
- 한국어 우회 경로:
  1. **[openwakeword.com](https://openwakeword.com/)** (비공식 학습 서비스): Kokoro TTS 67 voices로 ~13,000 합성 샘플 생성, **한국어 포함 30+개 언어** 지원 주장, ONNX 출력, 커뮤니티 모델 라이브러리 운영. 단 큐레이션 없음·품질 편차 고지([HA 커뮤니티 스레드](https://community.home-assistant.io/t/free-multilingual-wake-word-library-for-home-assistant-openwakeword-microwakeword/1016418)). 한국어 Kokoro 음성의 화자 다양성이 낮아 실사용 오탐/미탐 검증 필수.
  2. 자체 파이프라인: 한국어 TTS로 샘플 생성 + voice conversion 증강([Discussion #266](https://github.com/dscripka/openWakeWord/discussions/266)) — 비영어에서 양호한 모델을 얻었다는 커뮤니티 보고 있음. 공수 큼.
- 학습 자체는 Colab 노트북으로 1시간 내 가능하나, 자동 학습 노트북이 의존성 문제로 깨진 이력([Issue #296](https://github.com/dscripka/openWakeWord/issues/296)).

**유지보수 상태**
- 마지막 릴리스 **v0.6.0 (2025-02-11)**, 이후 17개월간 릴리스 없음. 이슈는 계속 쌓이나(2025-12 이슈 존재) 대응 둔화 — **저속 유지보수** 상태. [Releases](https://github.com/dscripka/openWakeWord/releases)
- 생태계는 건재: Home Assistant 애드온 표준, OVOS 플러그인 등.

**성능/부하**
- RPi3 1코어에서 15~20 모델 동시 실시간 → 모델 1개는 태블릿에서 수 % 수준. 입력 80ms(1280샘플) 청크.
- 목표 지표: **미탐률 <5%, 오탐 <0.5회/시간** — Porcupine 벤치 기준(0.1회/시간)보다 오탐 허용치가 느슨. 임계값+debounce 후처리 필수.

### 2.3 기타 대안

**microWakeWord — 제외**
- ESP32-S3/TFLite-micro 타깃의 초경량 프레임워크. Home Assistant Voice PE의 엔진. [ESPHome 문서](https://esphome.io/components/micro_wake_word/), [OHF-Voice/micro-wake-word](https://github.com/OHF-Voice/micro-wake-word)
- Android 포트 없음, 학습 파이프라인 영어 중심. 태블릿에서 굳이 마이크로컨트롤러용 모델을 쓸 이유 없음. **위성 노드(ESP32 스피커)를 나중에 추가할 때 재검토.**

**sherpa-onnx KWS — 제외(조건부)**
- Android 데모 APK 제공, open-vocabulary(키워드 텍스트 파일로 정의) 방식. [KWS 문서](https://k2-fsa.github.io/sherpa/onnx/kws/index.html)
- **사전학습 KWS 모델이 중국어/영어뿐 — 한국어 없음**([Pretrained models](https://k2-fsa.github.io/sherpa/onnx/kws/pretrained_models/index.html)). 한국어 KWS는 icefall로 인코더 자체 훈련 필요(대규모 한국어 음성 코퍼스 + GPU 훈련) — 현실성 낮음. 저인식률 이슈 리포트도 다수([Issue #2678](https://github.com/k2-fsa/sherpa-onnx/issues/2678)).
- 단, sherpa-onnx는 한국어 streaming zipformer STT/VAD를 이미 제공하므로 **STT·VAD 프로바이더로는 유력** — KWS만 제외.

**Vosk grammar/keyword mode — 폴백 후보**
- 한국어 small 모델 존재(~50MB급), Android 공식 지원. [모델 목록](https://alphacephei.com/vosk/models), [Android 가이드](https://alphacephei.com/vosk/android)
- grammar mode로 후보 어휘를 수십 개로 제한해 웨이크워드처럼 사용. `[unk]` 토큰 필수(미포함 시 엔진이 아무 말이나 워드로 붙잡음). 일본어 실전 사례: Silero VAD v5(2MB, 프레임당 0.3~0.8ms) 프리게이트 + Vosk grammar 조합으로 케어 환경에서 운용, TV 소리가 최대 오탐원. [zenn 실전기](https://zenn.dev/diced/articles/vosk-silero-vad-wakeword-android?locale=en)
- 장점: 라이선스 제약 전무(Apache-2.0), 완전 오프라인, 웨이크워드+간단 명령어 인식 겸용. 단점: 상시 ASR 디코딩이라 CPU/RAM 부담이 전 후보 중 최대, APK +50MB.

**LiveKit WakeWord — 관찰**
- 2026-02 v0.1.0 공개, Apache-2.0. Conv-Attention 분류기로 **openWakeWord 대비 오탐 ~100x 감소** 주장. VoxCPM2 TTS로 30+개 언어 합성 학습, YAML 한 줄 파이프라인, ONNX 출력. [GitHub](https://github.com/livekit/livekit-wakeword)
- 현재 Python/Rust/Swift만 — Android 미지원. ONNX라 onnxruntime-android 직접 통합은 가능. 한국어 합성 품질 미검증. **6개월 후 재평가 권장.**

---

## 3. CPU/배터리·오탐/미탐 비교

| 항목 | Porcupine | openWakeWord | Vosk grammar | sherpa-onnx KWS |
|---|---|---|---|---|
| 모델 크기 | ~1MB | ~수 MB(3단 합계) | ~50MB(ko small) | ~19-38MB |
| CPU(태블릿 환산) | ~1% 미만 | 수 % | 최대(상시 ASR) | 낮음(3.3M zipformer) |
| 오탐 벤치 | 1회/10h @97.1% | 목표 <0.5회/h | 사례상 TV 오탐 有 | 데이터 없음(ko 불가) |
| 한국어 커스텀 | Console 즉시 | 비공식 서비스/자작 | 어휘 나열로 즉시 | 사실상 불가 |
| 완전 오프라인 | 초기화만 온라인 | 완전 오프라인 | 완전 오프라인 | 완전 오프라인 |

- 항시 청취 배터리: 어느 엔진이든 마이크 상시 개방 비용이 지배적. 태블릿 허브는 상시 전원 거치 전제이므로 실질 이슈 낮음. 화면 꺼짐 대비 **foreground service + partial wakelock** 필수(Doze 회피).
- Porcupine은 자체 부하가 충분히 낮아 VAD 프리게이트 불필요. Vosk 폴백 시에만 Silero VAD 프리게이트 권장.

---

## 4. 추상화 인터페이스 설계 주의점 (WakeWordProvider)

1. **입력 계약 통일:** 엔진별 요구 프레임이 다름 — Porcupine 512샘플/프레임, openWakeWord 1280샘플(80ms), Vosk 임의 청크. 공용 `AudioCapture`(16kHz mono PCM)가 push하고, **각 어댑터 내부 ring buffer로 재프레이밍**. 인터페이스는 `processFrame(pcm: ShortArray)` 하나로.
2. **출력 계약:** `Flow<WakeEvent(keywordId, score, timestamp)>`. Porcupine은 이진 이벤트(내부 sensitivity), openWakeWord는 연속 score(임계값+debounce 후처리 필요) — **score 정규화와 debounce를 어댑터 책임**으로 두고 상위는 이벤트만 소비.
3. **감도 파라미터 추상화:** `sensitivity: Float(0~1)` 단일 노브 → Porcupine `sensitivity`에 직결, openWakeWord는 threshold 역매핑, Vosk는 grammar 후처리 규칙에 매핑.
4. **자산/자격 증명:** Porcupine `.ppn`+AccessKey, openWakeWord `.onnx/.tflite`, Vosk 모델 디렉터리 — provider 설정에 불투명 `params: Map<String,String>`로 수납, 설정 한 줄(`wakeword.provider=porcupine`) 교체 요건 충족.
5. **비동기 초기화 + 실패 모드:** Porcupine은 초기화 시 온라인 검증 → **네트워크 부재 시 초기화 실패를 명시적 오류 코드로 노출**하고 재시도/폴백(다른 provider로 자동 전환) 정책을 상위 레이어에 둘 것. 이것이 Porcupine 락인 리스크의 핵심 완충 장치.
6. **스레딩:** Vosk는 non-thread-safe(HandlerThread 직렬화 필요, zenn 사례), Porcupine/onnxruntime은 자체 스레드 안전 규약 상이 — 어댑터가 자기 실행 스레드를 소유하는 구조(단일 오디오 콜백 → 어댑터별 직렬 큐)로.
7. **마이크 소유권:** AudioRecord 인스턴스는 엔진 밖 공용 계층 1개만 — 웨이크워드→STT 핸드오프 시 마이크 재오픈 없이 스트림 분기(웨이크 검출 직후 버퍼 롤백 포함하면 첫 음절 유실 방지).

---

## 5. 참고 링크 모음

- Porcupine: https://picovoice.ai/products/voice/wake-word/ · https://picovoice.ai/docs/quick-start/porcupine-android/ · https://picovoice.ai/pricing/ · https://picovoice.ai/docs/faq/general/ · https://github.com/picovoice/porcupine
- openWakeWord: https://github.com/dscripka/openWakeWord · https://github.com/dscripka/openWakeWord/releases · https://openwakeword.com/ · https://github.com/Willy8m/openWakeWord-Android · https://github.com/dscripka/openWakeWord/discussions/266
- Home Assistant 관점: https://www.home-assistant.io/voice_control/about_wake_word/ · https://community.home-assistant.io/t/free-multilingual-wake-word-library-for-home-assistant-openwakeword-microwakeword/1016418
- microWakeWord: https://esphome.io/components/micro_wake_word/ · https://github.com/OHF-Voice/micro-wake-word
- sherpa-onnx KWS: https://k2-fsa.github.io/sherpa/onnx/kws/index.html · https://k2-fsa.github.io/sherpa/onnx/kws/pretrained_models/index.html
- Vosk: https://alphacephei.com/vosk/models · https://zenn.dev/diced/articles/vosk-silero-vad-wakeword-android
- LiveKit WakeWord: https://github.com/livekit/livekit-wakeword
