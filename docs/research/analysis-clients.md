# cozy-buddy 클라이언트 레포 분석 (hub / remote)

- 분석일: 2026-07-16
- 대상:
  - `cozy-buddy-hub` (Android Kotlin) — `scratchpad/cozy-buddy-hub`
  - `cozy-buddy-remote` (Flutter) — `scratchpad/cozy-buddy-remote`
- 기준 문서: `D:/workspace/etc/cozy/docs/cozy-buddy-design-v2.md` §10 (Android 허브 앱 구조)

---

## 1. cozy-buddy-hub (Android)

### 1-1. 저장소 개요

| 항목 | 값 |
|---|---|
| 커밋 수 | 4 (`Initial commit` → `chore: ignore 변경` → `chore: gradle setting` → `feat: Hilt DI 설정`) |
| 마지막 커밋 | **2025-12-03 13:04 (+0900)** — 약 7개월 전 중단 |
| 워킹트리 | clean (미커밋 작업물 없음) |
| 프로젝트명 | `CozyBuddyHub`, 모듈 `:app` 단일 |
| 패키지 | `piece.of.cake.cozybuddy` |

### 1-2. Gradle 설정

| 항목 | 값 | 비고 |
|---|---|---|
| compileSdk / targetSdk | **36** | |
| minSdk | 26 | |
| Kotlin | **2.0.21** | Compose Compiler는 `kotlin.plugin.compose` 2.0.21 (신방식) |
| AGP | **8.2.2 (실효)** — 루트 `build.gradle.kts`에 하드코딩 | 주의: `libs.versions.toml`의 `agp = 8.13.1`은 alias 미사용으로 **죽은 값**. AGP 8.2.2는 compileSdk 36 미지원(경고/실패 가능) → 정리 필요 |
| Hilt | **2.51.1** + KSP `2.0.21-1.0.27` | `hilt-android`, `hilt-compiler`, `hilt-navigation-compose 1.2.0` |
| Compose BOM | **2024.02.00** | 주의: 구버전(2년 경과). ui / ui-graphics / tooling-preview / **material3**만 포함 |
| 기타 | activity-compose 1.9.0, lifecycle-runtime(-compose) 2.8.7 | 버전 카탈로그와 직접 문자열 혼용 |
| Java | 17 (`kotlinOptions` 구문 — deprecated) | |

**없는 의존성(전부 미도입):** navigation-compose, kotlinx-serialization/Moshi, OkHttp(WebSocket), coroutines(명시), DataStore, TFLite/openWakeWord, Silero VAD, Timber, coil 등.

### 1-3. 구현된 코드 범위 — "어디서 멈췄나"

main 소스는 **Kotlin 파일 단 2개**:

- `CozyBuddyApp.kt` — `@HiltAndroidApp` 빈 Application
- `MainActivity.kt` — `@AndroidEntryPoint`, 가로모드 고정(Android 15 미만), `setContent { App() }`

핵심 문제: **MainActivity가 존재하지 않는 클래스를 import → 현재 컴파일 불가.**

```kotlin
import piece.of.cake.cozybuddy.core.ui.theme.AppColors        // 없음
import piece.of.cake.cozybuddy.core.ui.theme.AppThemeProvider // 없음
import piece.of.cake.cozybuddy.core.ui.theme.AppTypography    // 없음 (Pretendard 폰트 전제)
import piece.of.cake.cozybuddy.feature.home.ui.HomeScreen     // 없음
```

즉 마지막 작업은 "테마 시스템(`core/ui/theme`) + 홈 화면(`feature/home`)을 만들려던 직전"에서 중단. 커밋 `feat: Hilt DI 설정` 자체가 빌드 불가 상태로 남아 있음.

기타 관찰:

- **AndroidManifest: 권한 0개.** `INTERNET`, `RECORD_AUDIO`, `FOREGROUND_SERVICE(_MICROPHONE)`, `POST_NOTIFICATIONS`, `WAKE_LOCK` 전부 없음. Service/Receiver 선언 없음.
- `strings.xml`은 `app_name` 하나뿐 (i18n 리소스 미착수).
- 테스트는 템플릿 Example 2개뿐.
- import 경로로 보아 실제 채택하려던 패키지 컨벤션은 `core/` + `feature/<name>/ui` (**feature-by-package**)로, 설계문서 §10-1의 `presentation/` 레이어명과 **명칭이 다름** (아래 §3 참고).

### 1-4. 요약

> 사실상 **"Android Studio 템플릿 + Hilt 엔트리포인트"** 단계. 도메인 로직·오디오·네트워크·UI 전부 0%. 재개 시 첫 작업은 (1) AGP 버전 정리, (2) 누락된 theme/HomeScreen 생성으로 빌드 복구.

---

## 2. cozy-buddy-remote (Flutter)

| 항목 | 값 |
|---|---|
| 커밋 수 | **1** (`Initial commit`, 2025-10-31) |
| 내용물 | `README.md`(2줄) + Flutter용 `.gitignore` — **그 외 전무** |
| 상태 | **사실상 빈 레포 확인.** `flutter create` 스캐폴드조차 없음(`pubspec.yaml` 없음) |

README 상 목적: 터치 기반 원격 제어 컴패니언 앱. 설계 로드맵상 Phase 4(부차적 확장)이므로 현 시점 방치는 계획과 부합.

---

## 3. 설계문서 §10 대비 갭 분석

### 3-1. 패키지 구조 갭 (§10-1)

| §10-1 설계 | 목적 | hub 현황 |
|---|---|---|
| `di/` | Hilt 모듈 | 없음 (@HiltAndroidApp/@AndroidEntryPoint만, **모듈 0개**) |
| `core/audio/wakeword/` | `WakeWordEngine` 인터페이스 + OpenWakeWord/Porcupine | 없음 |
| `core/audio/vad/` | `VadEngine` + SileroVad | 없음 |
| `core/audio/capture/` | AudioRecord 16k mono PCM16 | 없음 |
| `core/audio/playback/` | StreamingAudioPlayer(AudioTrack) | 없음 |
| `core/network/` | WsClient(OkHttp) + FrameCodec + 재연결 | 없음 (OkHttp 의존성조차 미도입) |
| `service/VoiceForegroundService` | 상시 대기 루프 | 없음 (manifest 권한·service 선언도 없음) |
| `data/repository`, `data/ws` | Repository + §4 프로토콜 메시지 모델 | 없음 |
| `domain/model`, `domain/usecase` | HubState/Device/Room, UseCase | 없음 |
| `presentation/hub` | HubViewModel + 상태머신(StateFlow) | 없음 (ViewModel 0개) |
| `presentation/ambient` | 시계·날씨·포토프레임 | 없음 |
| `presentation/conversation` | 듣는중→처리중→응답 애니메이션 | 없음 |
| `presentation/devices` | 기기 카드 터치 제어 | 없음 |

**구현 커버리지: §10 항목 13개 중 0개 완성 (~0%). 존재하는 것은 Hilt 부트스트랩뿐.**

### 3-2. 핵심 설계 결정(§10-4 A1~A7) 대비

| # | 결정 | 현황 |
|---|---|---|
| A1 | Foreground Service 상시 대기 | 미착수 |
| A2 | WakeWord/VAD 인터페이스 + DI 교체 | 인터페이스 미정의 |
| A3 | 스트리밍 TTS + 바지-인 | 미착수 |
| A4 | KEEP_SCREEN_ON + 앰비언트 디밍 | 미착수 (가로모드 고정만 구현 — 유일하게 착수된 UX 결정) |
| A5 | 예쁜 UI(presentation 집중) | 착수 흔적만 — AppColors.dark / Pretendard 테마 시스템을 만들려던 import 존재, 실체 없음 |
| A6 | AEC (자기 TTS 반응 방지) | 미착수 |
| A7 | 마이크 어레이 권장 | HW 결정 사항, 코드 무관 |

### 3-3. 구조 컨벤션 불일치 (결정 필요)

- 설계 §10-1: `presentation/hub|ambient|conversation|devices` (레이어명 presentation).
- 실제 코드 의도(import 기준): `feature/home/ui` + `core/ui/theme` (**feature-first**).
- 또한 코드의 `feature/home`은 설계에 없는 화면 단위(설계는 hub/ambient/conversation/devices 4분할).
- → 재개 전에 **패키지 네이밍 하나로 통일** 필요. feature-first가 도메인 기반(P6) 철학과 더 부합하므로, 설계문서 쪽을 `feature/…`로 맞추거나 코드가 §10-1을 따르도록 선택해야 함.

### 3-4. 즉시 조치 목록 (재개 시 순서)

1. **빌드 복구**: `core/ui/theme/{AppColors,AppTypography,AppThemeProvider}` + `feature/home/ui/HomeScreen` 생성 (또는 MainActivity import 제거).
2. **Gradle 정리**: 루트 AGP 8.2.2 → toml `agp`(8.13.1+) alias로 일원화, 직접 문자열 의존성 전부 버전 카탈로그 이관, Compose BOM 최신화, `kotlinOptions`→`compilerOptions`.
3. **Manifest 권한/컴포넌트**: `INTERNET`, `RECORD_AUDIO`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MICROPHONE`, `POST_NOTIFICATIONS`, `WAKE_LOCK` + `VoiceForegroundService` 선언.
4. **의존성 도입**: OkHttp(WS), kotlinx-serialization, navigation-compose, DataStore, TFLite(openWakeWord), Timber.
5. 이후 §10 우선순위: `core/network`(WS+FrameCodec) → `core/audio/capture`+`vad` → 상태머신(HubViewModel) → wakeword → playback/바지-인 → ambient/devices UI.

### 3-5. 리스크 메모

- Compose BOM 2024.02.00 고정 상태로 개발 재개 시 material3 API 갭이 커짐 — 초기에 올려야 마이그레이션 비용 최소.
- AGP/카탈로그 이중 선언은 지금 고치지 않으면 compileSdk 36과 충돌해 첫 빌드부터 실패 가능.
- 마지막 커밋이 컴파일 불가 상태 → CI 없음이 확인됨. 최소한의 `assembleDebug` CI 도입 권장.

---

## 4. 결론 요약

- **hub**: 템플릿 + Hilt 골격(4커밋, 2025-12-03 중단). MainActivity가 미존재 테마/홈 화면을 참조해 **컴파일 불가**. §10 기능 커버리지 0%.
- **remote**: README+.gitignore뿐인 **빈 레포 확정** — Phase 4 계획과 일치, 현재 무시 가능.
- 갭의 본질: "설계 대비 미구현"이 아니라 **착수 직후 중단**. §10 전 항목이 그린필드이므로, 기존 코드 보존 부담 없이 설계문서 기준으로 재스캐폴딩하는 편이 빠름 (단, 패키지 컨벤션 feature-first vs presentation-레이어 결정 선행).
