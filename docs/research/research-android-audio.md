# Android 태블릿 상시 대기 음성 허브 — 플랫폼 제약 조사

- 프로젝트: cozy-buddy (자가호스팅 스마트홈 음성 AI 허브)
- 조사일: 2026-07-16
- 전제 시나리오: **전용 태블릿, 상시 전원 연결, 화면 상시 온, 단일 앱(키오스크)**

---

## 결론 요약 (TL;DR)

1. **마이크 FGS 제약은 "전용 단말 + 앱이 HOME(런처)" 구성으로 대부분 무력화된다.** 마이크 타입 FGS는 백그라운드/BOOT_COMPLETED에서 시작 불가(A14+)지만, 앱을 Device Owner + HOME 앱으로 만들면 부팅 직후 Activity가 자동 포그라운드 → 가시 상태에서 FGS 시작이므로 제약에 걸리지 않는다. Device Owner 앱은 while-in-use 제한 면제 대상이기도 하다.
2. **플랫폼 `AcousticEchoCanceler`는 신뢰 불가(기기 편차 극심).** 자기 TTS 되먹임 방지·바지-인은 **WebRTC AEC3(APM) 소프트웨어 AEC + 자기 TTS PCM을 reference로 직접 주입**하는 구조로 설계해야 한다. 자체 TTS라 재생 PCM을 이미 알고 있으므로 루프백 API 없이도 reference 확보 가능 — Android에서 가장 확실한 경로.
3. **상시 전원 태블릿에서는 Doze가 아예 발동하지 않고**(충전 중 Doze 미진입) FGS 보유 앱은 Doze 제한에서도 제외되므로, 16k mono 상시 캡처의 배터리/발열은 실질 비-이슈다. 진짜 발열원은 상시 화면이다(배터리 스웰링 주의).
4. **오디오 소스는 `VOICE_RECOGNITION` 기본 + 설정 교체 가능**하게. CDD는 VOICE_RECOGNITION에 AGC/NS 비활성을 요구하지만 OEM 편차가 실존(일부 기기 AGC 잔존 → Silero VAD 임계값 무의미화 사례). `UNPROCESSED`는 지원 선언 기기에서만 안전(미선언 기기·화웨이 등에서 무음 캡처 사례).
5. **오디오 파이프라인은 단일 AudioRecord → 팬아웃(ring buffer) 구조가 정석.** Silero VAD v5(onnxruntime-android, 512샘플/32ms 프레임, ~1ms/프레임)와 웨이크워드 엔진은 프레임 크기가 다르므로 소비자별 버퍼링 필수. 네이티브 엔진(Vosk 등)은 스레드 안전하지 않음 → 직렬화(HandlerThread) 필요.

---

## 1. 포그라운드 서비스(microphone 타입) 상시 마이크 캡처

### 1.1 버전별 제약 정리

| 버전 | 변경 사항 |
|---|---|
| Android 11 (API 30) | 카메라/마이크 사용 FGS는 해당 타입 선언 의무화 |
| Android 12 (API 31) | 백그라운드에서 FGS 시작 금지(예외 있음), `ForegroundServiceStartNotAllowedException` |
| Android 14 (API 34) | **모든 FGS 타입 선언 의무 + 타입별 권한**(`FOREGROUND_SERVICE_MICROPHONE`). while-in-use 권한 검사 강화: 백그라운드에서 mic FGS 생성 불가, **BOOT_COMPLETED 리시버에서 mic FGS 시작 불가** |
| Android 15 (API 35) | BOOT_COMPLETED 시작 금지 타입 확대(`dataSync`, `camera`, `mediaPlayback`, `phoneCall`, `mediaProjection` 추가). `SYSTEM_ALERT_WINDOW` 면제 축소(실제 가시 오버레이 창 필요). `dataSync`/`mediaProcessing` 6시간 타임아웃 |
| Android 16 (API 36) | FGS에서 시작한 백그라운드 잡(JobScheduler/WorkManager)에 런타임 쿼터 적용. **microphone 타입 자체에는 추가 타임아웃 없음** |

핵심: `microphone` 타입 FGS에는 (dataSync류와 달리) **시간제한이 없다**. 제약은 "언제/어떤 상태에서 시작할 수 있는가"에 집중되어 있다.

### 1.2 while-in-use 권한의 실제 의미

- `RECORD_AUDIO`는 while-in-use 권한: **앱이 포그라운드일 때만 유효**. 백그라운드 상태에서 mic FGS를 만들면 `SecurityException`(권한 체크 `checkSelfPermission()`은 백그라운드에서도 GRANTED를 반환하므로 사전 감지 불가 — Logcat에 "Foreground service started from background can not have ... microphone access" 출력).
- 단, **포그라운드(가시 Activity)에서 시작한 mic FGS는 이후 앱이 백그라운드로 가거나 화면이 꺼져도 마이크 접근을 유지**한다. 즉 "시작 시점"이 관건.
- while-in-use 제한 면제 대상: 시스템 컴포넌트 시작, 알림/위젯 상호작용, **Device Policy Controller(Device Owner)**, **`VoiceInteractionService` 제공자**, `START_ACTIVITIES_FROM_BACKGROUND` 보유 등.

### 1.3 화면 꺼짐 / Doze / 전용 태블릿

- **충전기 연결 중에는 Doze가 진입하지 않는다.** 또한 FGS(알림 포함) 보유 앱은 Doze/App Standby 제한 대상에서 제외. → 상시 전원 태블릿 허브에서는 Doze로 인한 캡처 중단은 사실상 없음.
- 화면 꺼짐 자체는 이미 시작된 mic FGS를 중단시키지 않는다(위 1.2). 단 OEM 배터리 매니저(삼성 "절전 앱", 중국계 OEM의 공격적 킬러)가 FGS를 죽이는 사례는 별개 리스크 → 배터리 최적화 제외(`ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`) + Device Owner로 이중 방어.
- Android 12+ 상시 마이크 사용 시 **프라이버시 인디케이터(녹색 점)** 상시 표시, QS 마이크 토글로 사용자가 하드 뮤트 가능 — 전용 단말에서는 UX 이슈 아님(오히려 신뢰 신호로 활용 가능).

### 1.4 cozy-buddy 권장 구성

```
부팅 → (Device Owner) 앱 = HOME 앱으로 자동 실행(가시 Activity)
     → Activity에서 startForegroundService(mic 타입) ← "가시 상태 시작"이라 합법
     → KEEP_SCREEN_ON으로 계속 포그라운드 유지 → 제약 자체가 발생하지 않음
```
- BOOT_COMPLETED 리시버에서 mic FGS를 직접 시작하는 설계는 **금지**(A14+에서 예외). HOME 앱 자동 기동 경로로 우회.
- 대안 경로: 앱을 기기 **어시스턴트 앱(`VoiceInteractionService`, ROLE_ASSISTANT)** 으로 등록하면 while-in-use 면제 + 핫워드 관련 특권 획득. 단 DSP 기반 `AlwaysOnHotwordDetector`(SoundTrigger HAL)는 시스템/OEM 통합이 필요해 3rd-party에겐 비현실적 — CPU 웨이크워드가 정답(§5).

출처:
- https://developer.android.com/develop/background-work/services/fgs/service-types
- https://developer.android.com/develop/background-work/services/fgs/changes
- https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
- https://developer.android.com/about/versions/15/behavior-changes-15
- https://developer.android.com/training/monitoring-device-state/doze-standby
- https://source.android.com/docs/core/power/platform_mgmt

---

## 2. AEC — 자기 TTS 되먹임 방지와 바지-인

### 2.1 플랫폼 `AcousticEchoCanceler`의 실태

- `android.media.audiofx.AcousticEchoCanceler`는 **OEM HAL 구현의 래퍼**. `isAvailable()`이 true여도 실효성은 기기마다 극단적으로 다름(우수 ↔ 사실상 no-op). `MODIFY_AUDIO_SETTINGS` 필요, AudioRecord의 audioSessionId에 attach.
- 다수 기기에서 HW AEC는 `VOICE_COMMUNICATION` 소스 경로에서만 활성화되며, 통화(근접 발화) 기준으로 튜닝되어 **원거리(far-field) 발화 + 대음량 TTS 재생** 시나리오에서는 성능 저하가 흔함. VOICE_COMMUNICATION 경로는 공격적 NS/AGC가 함께 걸려 웨이크워드/VAD 정확도를 해칠 수 있음.
- 결론: **기기 편차 때문에 플랫폼 AEC를 1차 수단으로 삼으면 안 됨.** 다수 음성 앱이 플랫폼 AEC를 우회하고 WebRTC AEC3를 직접 탑재하는 것이 업계 관행.

### 2.2 권장: WebRTC AEC3(APM) 소프트웨어 AEC

- WebRTC APM 처리 순서: HPF → **AEC3** → NS → AGC2. AEC3는 주파수영역 분할블록 적응필터(PBFDAF) 기반으로 모바일에서 **20~200ms의 가변 지연**을 딜레이 추정으로 흡수.
- **cozy-buddy의 결정적 이점: TTS를 자기가 재생하므로 reference 신호(재생 PCM)를 이미 보유.** Android에는 앱 오디오 루프백 API가 없지만(타 앱 캡처는 MediaProjection 필요), 자기 TTS PCM을 APM의 reverse stream(`ProcessReverseStream`)에 그대로 넣으면 됨. 재생 경로 지연은 AEC3 딜레이 추정이 보정.
- 지연 안정화를 위해 **Oboe(AAudio, 저지연/MMAP 경로)** 로 재생·캡처를 통일하면 AEC 수렴이 빨라짐. Oboe 자체엔 AEC 없음 — `InputPreset::VoiceCommunication`으로 HW AEC를 켜는 옵션도 있으나(§2.1 한계) SW AEC 조합이 기본값으로 적절.

### 2.3 바지-인(barge-in) 설계

- 바지-인 = TTS 재생 중 사용자 발화 감지. AEC 출력 위에서 웨이크워드/VAD를 돌리는 것이 전제.
- AEC 없이 방치하면 **자기 TTS의 키워드에 스스로 반응하는 self-wake 무한루프** 발생(문헌 확인됨).
- 계층 방어 권장:
  1. AEC3 출력에서 VAD/WW 실행 (1차)
  2. TTS 재생 중 VAD/WW 임계값 상향 (2차)
  3. 실패 시 폴백: TTS 재생 중 WW 게이팅(half-duplex) — 바지-인 포기 모드를 **설정으로 제공**
- AEC 모듈 자체를 provider 인터페이스로 추상화: `NoopAec` / `PlatformAec` / `WebRtcAec3` 교체 가능하게.

출처:
- https://developer.android.com/reference/android/media/audiofx/AcousticEchoCanceler
- https://switchboard.audio/hub/how-webrtc-aec3-works/
- https://www.coval.ai/blog/voice-ai-echo-cancellation/
- https://arxiv.org/pdf/2111.10639 (Implicit AEC for KWS — self-wake 문제 기술)
- https://www.forasoft.com/learn/audio-for-video/articles-audio/webrtc-audio-pipeline-end-to-end

---

## 3. 상시 캡처의 전력/발열 + 오디오 소스 선택

### 3.1 전력/발열 (상시 전원 태블릿 기준)

- 16kHz mono 16bit = **32KB/s**. 데이터량은 무시 수준. 전력 비용의 본질은 (a) 마이크/오디오 경로 상시 활성 (b) CPU 웨이크워드 추론.
- 배터리 구동 기준 참고치: 경량 웨이크워드(Porcupine류) 상시 청취 10~15시간 vs 풀 STT 상시 6~8시간 → 웨이크워드 게이팅이 CPU 비용을 수 배 절감. **상시 전원에서는 어차피 비-이슈이나, 발열·수명 관점에서 같은 구조가 유효.**
- **진짜 발열/수명 리스크는 상시 화면 + 상시 충전**: 배터리 스웰링(24/7 키오스크의 고질병), OLED 번인. 대응: 밝기 20~30% 감축, 급속충전 회피(가능하면 충전 상한 85% 기능 있는 기기 선정), 야간 디밍/스크린세이버, 통풍 확보.

### 3.2 VOICE_RECOGNITION vs UNPROCESSED

| 소스 | 규격상 처리 | 실전 주의 |
|---|---|---|
| `VOICE_RECOGNITION` | CDD 5.4: **NS·AGC 기본 비활성 의무(MUST)**, 100–4000Hz ±3dB 평탄 응답(SHOULD) | OEM 편차 실존 — 일부 기기에서 AGC 잔존 보고. AGC가 살아 있으면 Silero VAD 확률값이 흔들려 튜닝한 임계값이 무의미해짐(실측 사례) |
| `UNPROCESSED` | 전 처리 없음(raw) | `AudioManager.getProperty(PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED)` 선언 기기에서만 보장. 미보장 기기에서 조용히 무음 캡처되는 사례(화웨이 등) |
| `VOICE_COMMUNICATION` | HW AEC/NS/AGC 경로 | HW AEC 활용시에만. 통화 튜닝이라 far-field 왜곡 위험 |
| `MIC` (DEFAULT) | OEM 임의 처리 | 비권장 |

- **권장 기본값: `VOICE_RECOGNITION`**, `UNPROCESSED`는 지원 확인 후 옵션. cozy-buddy의 provider 패턴에 맞게 **audioSource를 설정 한 줄로 교체 가능**하게 하고, 최초 셋업 시 실기기 캡처 테스트(레벨/AGC 여부 검사) 루틴 내장 권장 — "반드시 실기기에서 전 소스 테스트"가 업계 공통 결론.

출처:
- https://android.googlesource.com/platform/compatibility/cdd/+/refs/tags/platform-tools-31.0.0/5_multimedia/5_4_audio-recording.md
- https://developer.android.com/reference/android/media/MediaRecorder.AudioSource
- https://picovoice.ai/blog/android-speech-recognition/
- https://ai.plainenglish.io/training-a-wake-word-model-that-actually-works-on-your-phone-a5925e12e207 (소스별 DSP 체인 편차, 화웨이 UNPROCESSED 무음 사례)
- https://lavalink.com/lavablog/articles/is-your-tablets-battery-bloating-4-tips-to-avoid-this-issue/ (24/7 충전 스웰링)

---

## 4. 키오스크/전용 단말 구성

### 4.1 두 가지 레벨

| 방식 | 설정 | 강도 | 한계 |
|---|---|---|---|
| Screen Pinning (사용자) | 설정 메뉴/`startLockTask()`(비-DO) | 약 | 핀 해제 제스처로 탈출 가능, 확인 다이얼로그 표출 |
| **Lock Task Mode (Device Owner)** | DO가 `setLockTaskPackages()` 허용 후 `startLockTask()` | 강 | 상태바/홈/최근앱 차단, 탈출 불가 — **전용 단말 표준** |

### 4.2 Device Owner 셋업 (개인 프로젝트 최적 경로)

```bash
# 공장초기화 직후, Google 계정 추가 전
adb shell dpm set-device-owner com.cozy.buddy/.AdminReceiver
```
- 루팅 불필요. QR/NFC 프로비저닝(Android Enterprise)도 가능하나 개인 1대는 adb가 최단.
- DO가 되면: `setLockTaskPackages`, `addPersistentPreferredActivity`(HOME 고정), `setKeyguardDisabled(true)`(잠금화면 제거), `setGlobalSetting(STAY_ON_WHILE_PLUGGED_IN, ...)`(충전 중 화면 유지), 시스템 업데이트 정책 제어 등.
- §1.2와 연결: **DO 앱은 FGS 백그라운드 시작 제한·while-in-use 제한 면제 목록에 포함** → 마이크 FGS 제약의 구조적 해결책.

### 4.3 화면 상시 온

- 1차: Activity에 `WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON`(권한 불필요, 포그라운드 Activity 동안만).
- 2차(보강): DO의 `STAY_ON_WHILE_PLUGGED_IN` 글로벌 설정 — 충전 중 화면 꺼짐 자체를 차단.
- 번인 대책: 야간 저휘도 시계 화면 등 픽셀 회전 콘텐츠(Nest Hub의 Ambient 모드 벤치마킹 포인트).

### 4.4 부팅 자동 시작 제약

- `RECEIVE_BOOT_COMPLETED` 리시버에서 **Activity 직접 실행은 Android 10+ 백그라운드 Activity 시작 제한으로 차단**, mic FGS 시작도 A14+ 금지(§1).
- 정석 해법: **DO의 `addPersistentPreferredActivity()`로 앱을 HOME(런처) 기본 처리자로 등록** → 부팅 완료 시 시스템이 앱을 자동 기동(가시 Activity) → 거기서 `startLockTask()` + mic FGS 시작. `startLockTask()`는 재부팅 간 비지속이므로 매 부팅 재진입 로직 필요.
- 잠금화면: DO `setKeyguardDisabled(true)`로 제거(미제거 시 재부팅 후 키가드 뒤에서 멈춤). Direct Boot(암호화 저장소) 이슈도 함께 소멸.

출처:
- https://developer.android.com/work/dpc/dedicated-devices/lock-task-mode
- https://developers.google.com/android/management/policies/dedicated-devices
- https://quantem.io/feeds/blog/android-kiosk-mode-programmatically (adb DO 셋업, BootReceiver + addPersistentPreferredActivity 패턴)
- https://dev.to/vantagemdm/android-kiosk-mode-the-ultimate-guide-to-locking-down-devices-140k

---

## 5. Silero VAD(onnxruntime-android) + 웨이크워드 파이프라인 공유

### 5.1 Silero VAD 구동 스펙 (실전 검증치)

- 런타임: `com.microsoft.onnxruntime:onnxruntime-android`(1.17+), 모델 assets 로드, ABI는 arm64-v8a 중심.
- **v5: 512샘플(32ms@16k) 고정 프레임**, 입력은 Float32 정규화(`short / 32768f`). 추론 ~0.3–1ms/프레임(실시간 대비 수십 배 여유) — CPU로 충분.
- 주의: NNAPI EP는 Android 15에서 플랫폼 차원 deprecated → **EP는 기본 CPU(XNNPACK)로 고정** 권장. 이 크기 모델엔 NPU 오프로드 이득 없음.
- v6는 큰 청크 직접 추론 미지원 → 슬라이딩 윈도/버퍼링 필요. 버전 pin 필수(모델 파일도 provider 설정에 포함).

### 5.2 파이프라인 공유 구조 (핵심 설계)

```
AudioRecord (단일 인스턴스, 16k mono s16, VOICE_RECOGNITION)
   └─ 캡처 스레드 1개 → lock-free ring buffer(pre-roll 겸용, 1~2s)
        ├─ [소비자 A] WakeWord 엔진 (예: openWakeWord 1280샘플/80ms 프레임)
        ├─ [소비자 B] Silero VAD (512샘플/32ms 프레임)
        └─ [소비자 C] STT 스트리머 (웨이크 후 활성, pre-roll 포함 전송)
```

주의점(조사에서 확인된 함정):
1. **AudioRecord는 반드시 1개.** 복수 인스턴스는 기기별로 실패하거나 마이크 점유 충돌(Android 10+ 동시 캡처 우선순위 규칙). 팬아웃은 앱 내부에서.
2. **프레임 크기 불일치**: WW 엔진(Porcupine 512, openWakeWord 1280, sherpa-onnx KWS 가변)과 VAD(512)의 요구 프레임이 다름 → 소비자별 독립 버퍼링/리샘플 어댑터 계층 필요. 이 어댑터가 provider 추상화의 자연스러운 경계.
3. **네이티브 엔진 스레드 안전성**: Vosk 등 C++ 엔진은 내부 mutex 없음 → 코루틴 Dispatchers.IO 병렬 호출 시 크래시. 엔진당 단일 HandlerThread(또는 single-thread executor)로 직렬화.
4. **AGC와 VAD 임계값**: 소스에 AGC가 걸려 있으면 Silero 확률값 변동으로 임계값(예: 0.5~0.65) 튜닝이 무효화(§3.2). 소스 선택과 VAD 임계값은 한 세트로 설정화.
5. **VAD로 WW를 게이팅해 CPU 절약 가능하나 발화 온셋 손실 위험** → pre-roll ring buffer(0.5~1s)로 웨이크 감지 시점 이전 오디오까지 STT에 전달(웨이크워드 잘림/첫 음절 손실 방지).
6. **AEC 위치**: AEC3 출력이 ring buffer에 들어가야 함(원신호 아님). 즉 캡처 스레드에서 `mic → APM(AEC3) → ring buffer` 순서.
7. 대안 통합 스택: **sherpa-onnx**(k2-fsa)는 KWS(open-vocab 커스텀 키워드)+VAD+스트리밍 STT를 onnxruntime 단일 런타임으로 제공, Android arm64 공식 지원 — 한국어 커스텀 웨이크워드("코지야" 등)를 재학습 없이 지정 가능해 cozy-buddy 후보로 유력.

출처:
- https://zenn.dev/diced/articles/vosk-silero-vad-wakeword-android (실전 파이프라인: AGC 이슈, 512프레임, HandlerThread 직렬화, NNAPI 수치)
- https://github.com/snakers4/silero-vad/discussions/738 (v6 청크 제약)
- https://github.com/helloooideeeeea/RealTimeCutVADLibraryForAndroid (Silero+WebRTC APM 결합 선례)
- https://github.com/k2-fsa/sherpa-onnx / https://k2-fsa.github.io/sherpa/onnx/kws/index.html
- https://picovoice.ai/blog/complete-guide-to-wake-word/

---

## 6. cozy-buddy 아키텍처 반영 권고

1. **단말 구성**: 공장초기화 → adb Device Owner → HOME 고정 + Lock Task + Keyguard 해제 + STAY_ON_WHILE_PLUGGED_IN. 이 구성이 §1의 FGS 제약을 구조적으로 제거하는 유일한 "설계로 푸는" 경로.
2. **오디오 계층 추상화 경계**: `AudioSourceProvider`(소스/샘플레이트) → `AecProvider`(Noop/Platform/WebRtcAec3) → `FanOutBus`(ring buffer) → `WakeWordProvider` / `VadProvider` / `SttStreamProvider`. 각 provider 설정 한 줄 교체 요구사항과 정합.
3. **바지-인은 v1 옵션 기능으로**: AEC3 통합 난도가 가장 높음. v1은 half-duplex(TTS 중 WW 게이팅) 폴백을 기본값으로, AEC3 경로를 플래그로 열어 점진 검증.
4. **기기 선정 체크리스트**: LCD(번인 회피) 우선, 충전 상한 기능, `PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED` 여부, 멀티마이크(원거리 수음), 순정에 가까운 OS(공격적 앱 킬러 회피 — 삼성/중국계 OEM 주의).
