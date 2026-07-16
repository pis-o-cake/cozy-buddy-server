# IoT 제어 계층 설계 조사 — cozy-buddy (2026-07-16)

> 대상: 자가호스팅 Python 서버(Windows, RTX 5080)에서 IoT 기기를 어댑터 패턴으로 제어.
> 결론 요약: **"직접 어댑터 우선 + HA 어댑터 슬롯" 하이브리드 권장** (§6).

---

## 1. 직접 제어: python-kasa / plugp100 / Tapo 클라우드 vs LAN

### 1.1 python-kasa (권장 1순위)
- **현행 지원 (v0.10.x, 2025-02 릴리스 이후 활발 유지보수)**: TP-Link **Kasa + Tapo 통합** 라이브러리.
  Tapo 플러그(P100/P105/P110/P110M/P115/P125M/P135), 전원 스트립, 벽 스위치, 전구/라이트스트립,
  **카메라·도어벨·로봇청소기·허브(H100)** 까지 지원 범위 확대됨.
- **HA 공식 `tplink` 통합의 백엔드 라이브러리** — 사실상 TP-Link 계열의 표준 구현체. 유지보수 신뢰도 높음.
- **프로토콜**: 구형 Kasa = IOT(XOR) 프로토콜, Tapo/신형 Kasa = **SMART 프로토콜 + KLAP 전송**(HTTP :80).
  TP-Link가 2023년부터 AES 공개키 교환 방식의 취약점 때문에 KLAP 암호화로 펌웨어 전환 중.
- **디스커버리**: UDP 브로드캐스트(255.255.255.255). 신형 기기는 포트 20002로 디스커버리.
- **주의**: Tapo 및 신형 Kasa는 **인증 필수** — TP-Link 클라우드 계정 자격증명(해시)이 로컬 KLAP
  핸드셰이크에 쓰임. 펌웨어가 KLAP으로 넘어간 직후 인증 오류 이슈 보고 사례 있음(라이브러리 업데이트로 추종).

### 1.2 plugp100 및 기타 대안
- **plugp100** (petretiandrea): Tapo 프로토콜의 WIP 구현. HA 커스텀 통합 `home-assistant-tapo-p100`의
  백엔드. python-kasa가 Tapo를 공식 흡수한 이후 **차별 우위 상실** — 신규 프로젝트에서 선택할 이유 약함.
- **tapo** (mihai-dinculescu): Rust 코어 + Python 바인딩. 성능은 좋으나 기기 커버리지·커뮤니티가 python-kasa 대비 좁음.
- **PyP100**: 구세대, KLAP 미대응 이슈 — 제외.

### 1.3 Tapo 클라우드 vs LAN 로컬
- **제어 자체는 LAN 로컬로 완결** 가능(KLAP도 로컬 HTTP). 단 자격증명이 클라우드 계정 기반이라
  "계정 없는 완전 오프라인"은 아님. 인터넷 차단 시 주기적 credential sync 실패로
  'Invalid authentication'이 뜰 수 있다는 커뮤니티 보고 있음.
- **완전 로컬(계정 무관)을 원하면**: Matter 인증 Tapo 기기(S505/S515 스위치 등)를 Tapo 앱에서 제거 후
  **Matter 커미셔닝(QR)** 으로 붙이면 클라우드 계정 없이 로컬 제어 가능 — §2의 Matter 어댑터 경로와 합류.

**어댑터 설계 시사점**: `KasaTapoAdapter`는 python-kasa 단일 의존성으로 구현. 설정에
`username/password`(Tapo 계정) 슬롯 필요. 디스커버리는 브로드캐스트 + 수동 IP 등록 병행.

---

## 2. Matter: 독립 컨트롤러 구성

### 2.1 python-matter-server → matterjs-server (중대 변경)
- **python-matter-server는 v8.1.2가 최종 버전 — deprecated.** 2025-11 Open Home Foundation이
  matter.js 기반 **matterjs-server** 로 전면 재작성·이관 발표. python 서버는 더 이상 업데이트/지원 없음.
  HA도 2026.2 즈음 애드온 9.0.0에서 matter.js 서버로 마이그레이션 진행.
- **matterjs-server 특징**:
  - python-matter-server와 **호환되는 WebSocket 인터페이스** 제공(drop-in replacement). 기본 `localhost:5580/ws`.
  - **standalone Docker 컨테이너로 HA 없이 독립 실행 가능** (원래 python-matter-server도 "universal
    approach, 다른 프로젝트에서 사용 가능"이 공식 입장).
  - Matter **1.4.2** 지원. 클라이언트 패키지: `@matter-server/ws-client` (JS) — Python에서는
    WebSocket JSON-RPC를 직접 말하거나 기존 python-matter-server 클라이언트 프로토콜 호환 사용.
- **cozy-buddy 시사점**: `MatterAdapter`는 matterjs-server 컨테이너(WSL2/Docker Desktop)에
  WebSocket으로 붙는 **클라이언트**로 구현. 서버 프로세스 자체를 우리가 재구현할 필요 없음.
  주의: Windows 호스트에서 mDNS/IPv6 요구사항 때문에 **host 네트워크가 되는 Linux 컨테이너 환경**(WSL2)
  구성이 관건 — 공식 권장은 Linux host-network Docker.

### 2.2 커미셔닝(QR)·Thread 보더라우터
- **Wi-Fi Matter 기기**: 서버에 QR/페어링 코드로 직접 커미셔닝 가능. BLE 온보딩은 `--ble` 플래그로
  지원되나 제약 있음(BLE 어댑터 필요, `--ble-proxy` 로 원격 어댑터 분리 가능). 스마트폰 없이
  커미셔닝하는 절차가 HA 커뮤니티 가이드로 정리되어 있음.
- **Thread Matter 기기**: **Thread 보더라우터(TBR) 별도 필요** — 서버 소프트웨어만으로 불가.
  선택지: Nest Hub/HomePod 등 기존 TBR 재활용, 또는 SLZB-06/ZBT-1 + OpenThread Border Router.
  2026 시점에도 TBR 간 크레덴셜 공유(Thread 1.4)는 **같은 생태계 안에서만 원활**, 생태계 간 "Thread island"
  문제 잔존.
- **어댑터 설계 시사점**: 1차 릴리스는 **Matter over Wi-Fi만 지원**(TBR 불요), Thread는
  "TBR 있으면 사용" 옵션으로.

### 2.3 2026 시점 Matter 생태계 성숙도
- 인증 기기 750~1,100+개(집계 기준 차이)로 급성장. Matter 1.4(에너지, HRAP)·1.5(카메라) 공개.
- 평가: "**2026년은 Matter가 대부분의 유스케이스에서 실제로 작동하는 첫 해**". 단 플랫폼 파편화
  여전(다수 생태계가 1.2/1.3에 머묾), multi-admin 폴링으로 배터리 소모 증가, 기기 스펙 표기 불투명.
- 삼성이 TBR 내장 기기를 조용히 확대 중, LG는 2025+ 모델 일부 Matter over Thread 인증.
- **판단**: 플러그/전구/스위치/센서 등 기본 카테고리는 Matter로 충분히 실용. 백색가전(세탁기·냉장고)은
  Matter 매핑이 아직 부분적 → 클라우드 API(§3) 병행 필요.

---

## 3. Home Assistant 연동 어댑터

### 3.1 기술 방식
- HA **WebSocket API**(`/api/websocket`) + REST API. 장기 액세스 토큰(Long-lived token) 인증.
  `call_service` 로 제어, `subscribe_events(state_changed)` 로 상태 push 수신 — 어댑터에 이상적.
- 기성 Python 클라이언트: **python-hass-client**(Music Assistant 프로젝트, asyncio) 권장.
  대안: hassapi, homeassistant_api, hass-websocket-client.

### 3.2 직접 어댑터 대비 장단점
| 항목 | 직접 어댑터 | HA 어댑터 |
|---|---|---|
| 커버리지 | 라이브러리별 개별 구현 | **약 3,000개 통합 즉시 흡수** |
| 설치 부담 | pip 의존성 수준 | HA 상시 실행(컨테이너/VM) + 이중 관리(HA UI) |
| 레이턴시 | LAN 직결(최단) | +1 hop(무시 가능 수준, LAN 내 WebSocket) |
| 장애면 | 어댑터별 독립 | HA 다운 = 전체 다운(단일 장애점) |
| 엔티티 모델 | 우리가 정의 | HA 도메인 모델(light/switch/climate...)을 그대로 매핑 — 표준화 이점 |

### 3.3 국내 가전 커버 (핵심 변수)
- **LG ThinQ**: HA **공식 통합**(2024.11 도입, ThinQ Connect API 기반, 클라우드). 활성 설치 4.4%로 성장.
  직접 구현하려면 `thinqconnect` SDK(LG 공식 오픈 API)로도 가능하나, 기기별 프로파일 매핑 비용이 큼 → HA 경유가 실용적.
- **삼성 SmartThings**: HA 공식 통합이 2025년 **OAuth 기반으로 전면 재작성**(cloud push, 실시간).
  단, **중대 리스크: Samsung이 2026-10부터 SmartThings API 무료 접근 종료 — personal plan $4.99/월 유료화 발표.**
  HA 창립자 Paulus Schoutsen이 HA SmartThings 통합도 영향권임을 확인(HA 활성 설치의 약 9.8%, ~20만 설치 영향 추정).
  → 삼성 기기는 장기적으로 **Matter 경로(삼성 TBR/Matter 브리지)로 우회**하는 설계가 안전.

---

## 4. MQTT / Zigbee2MQTT 확장 슬롯
- **Zigbee2MQTT**: USB Zigbee 코디네이터 + MQTT 브로커(Mosquitto)만으로 HA 없이 완전 로컬 동작.
- 제어 프로토콜이 단순·안정: `{base_topic}/{friendly_name}/set` 에 JSON publish, 상태는
  `{base_topic}/{friendly_name}` 구독, 관리작업은 `bridge/request/...` → `bridge/response/...` 패턴.
  기기 capability는 `exposes` 메타데이터로 자동 열거 가능 — **어댑터의 동적 기기 모델링에 최적**.
- **어댑터 설계 시사점**: `MqttAdapter`(범용) 위에 `Zigbee2MqttAdapter`(exposes 파서)를 얹는 2단 구조.
  라이브러리는 `aiomqtt` 권장. Zigbee 하드웨어 도입 전까지는 빈 슬롯으로 두면 됨(브로커는 선택 설치).

---

## 5. 어댑터 계층 설계 (요구사항의 provider 패턴 적용)

```
IoTAdapter (ABC)                       # discover / get_state / execute / subscribe
 ├─ KasaTapoAdapter    → python-kasa (LAN 직결)          [1차]
 ├─ MatterAdapter      → matterjs-server WS 클라이언트    [1차, Wi-Fi 기기부터]
 ├─ HomeAssistantAdapter → WebSocket API (python-hass-client) [슬롯: 국내가전용]
 └─ MqttAdapter/Zigbee2MqttAdapter → aiomqtt              [슬롯: Zigbee 도입 시]
```
- 공통 기기 모델(디바이스/capability 스키마)로 정규화 → LLM tool-calling 이 어댑터 무관하게 동작.
- 설정 예: `iot.adapters: [kasa, matter]` + adapter별 섹션 — 설정 한 줄 교체 요구 충족.

---

## 6. 결론: "직접 어댑터 우선 + HA 어댑터 슬롯" 권장

**"처음부터 HA 위임"이 아닌 하이브리드가 낫다.** 근거:

1. **1차 타깃(플러그·전구·스위치 음성 제어)은 직접 어댑터로 충분** — python-kasa 하나로 Tapo/Kasa
   전 계열 LAN 제어, matterjs-server 컨테이너 하나로 Matter 표준 커버. HA 설치·관리 부담 없이
   pip + 컨테이너 1개로 끝. Nest Hub 벤치마크의 기기 제어 범주를 로컬 우선으로 충족.
2. **HA 전면 위임은 오버킬 + 단일 장애점** — cozy-buddy의 차별점은 음성/LLM 계층이며, HA를 깔면
   상시 서비스·업데이트·UI 이중 관리가 생기고 모든 제어가 HA 가용성에 종속됨. 또 HA가 흡수해 주는
   가치의 대부분(수천 통합)은 실제 보유 기기 수 개에는 과잉.
3. **단, HA 어댑터 슬롯은 반드시 확보** — LG ThinQ·기타 클라우드 가전은 직접 구현 비용이 크고
   HA 공식 통합이 이미 검증됨. `HomeAssistantAdapter`는 WebSocket 클라이언트 1개 구현 비용으로
   "필요할 때 수천 통합"을 여는 보험. 인터페이스만 맞추면 나중에 켜는 데 비용이 거의 없음.
4. **삼성 SmartThings는 2026-10 API 유료화 리스크** — HA 경유든 직접이든 동일하게 맞는 리스크이므로,
   삼성 기기는 Matter 경로를 1순위로 설계.
5. **Matter 어댑터는 python-matter-server가 아닌 matterjs-server 기준으로 구현** — python 서버는
   8.1.2로 종료(deprecated). WS 프로토콜이 호환이므로 어댑터 코드는 서버 교체와 무관하게 유지됨.

### 단계별 로드맵
- **Phase 1**: `KasaTapoAdapter`(python-kasa) — 즉시 체감, 의존성 최소.
- **Phase 2**: `MatterAdapter`(matterjs-server, Wi-Fi 커미셔닝) — 표준 확장.
- **Phase 3(옵션)**: `HomeAssistantAdapter` — LG ThinQ 등 클라우드 가전 필요 시점에 활성화.
- **Phase 4(옵션)**: `Zigbee2MqttAdapter` — Zigbee 센서류 도입 시.

---

## 출처
- python-kasa GitHub / 문서: https://github.com/python-kasa/python-kasa , https://python-kasa.readthedocs.io/en/latest/ , https://python-kasa.readthedocs.io/en/stable/SUPPORTED.html
- KLAP 전환 논의: https://github.com/python-kasa/python-kasa/discussions/559 , https://community.tp-link.com/us/smart-home/forum/topic/861124?moduleId=2430
- plugp100: https://github.com/petretiandrea/plugp100 / tapo(Rust): https://pypi.org/project/tapo/
- Tapo Matter 로컬 제어: https://community.home-assistant.io/t/do-tapo-matter-smart-switches-require-cloud-account-for-local-only-operation/909584
- python-matter-server (deprecated 고지): https://github.com/matter-js/python-matter-server
- matterjs-server: https://github.com/matter-js/matterjs-server , HA 새 Matter 서버 베타: https://matter-smarthome.de/en/development/home-assistant-launches-beta-of-new-matter-server/
- HA 2026.2 마이그레이션: https://community.home-assistant.io/t/migration-of-python-matter-server-docker-container-to-matter-js-with-ha-2026-2/981070
- 스마트폰 없이 Matter 커미셔닝: https://community.home-assistant.io/t/commissioning-matter-devices-with-the-matter-server-without-smartphone-and-or-matter-add-on/905051
- Matter 2026 현황: https://matter-smarthome.de/en/development/the-matter-standard-in-2026-a-status-review/ , Thread 1.4/TBR 문제: https://fixoryhq.com/en/thread-14-border-router-explained/
- HA WebSocket 클라이언트: https://github.com/music-assistant/python-hass-client , https://developers.home-assistant.io/docs/frontend/extending/websocket-api/
- LG ThinQ 공식 통합: https://www.home-assistant.io/integrations/lg_thinq/
- SmartThings 통합(OAuth 재작성): https://www.home-assistant.io/integrations/smartthings/ , https://community.home-assistant.io/t/smartthings-2025-oauth/860625
- SmartThings API 유료화: https://blog.smartthings.com/smartthings-updates/a-new-enhanced-smartthings-api-experience/ , https://www.androidauthority.com/smarthings-api-paid-tiers-3681929/ , https://www.howtogeek.com/samsung-smartthings-api-price-for-access/
- Zigbee2MQTT MQTT 토픽: https://www.zigbee2mqtt.io/guide/usage/mqtt_topics_and_messages.html
