"""기기 taxonomy (설계서 §8-1) — 새 타입 추가는 이 파일 한 곳만 수정.

- device_type = 용도(LLM이 이해하는 어휘)
- capability = 타입 기본 프로파일 ∩ 어댑터 실지원
- control_device tool의 capability enum은 여기서 동적 생성한다 (§7-2 — 하드코딩 금지)
"""

# 타입별 기본 capability 프로파일
DEVICE_TYPES: dict[str, set[str]] = {
    # 조명류
    "light": {"on_off", "brightness", "color_temp"},
    "lamp": {"on_off", "brightness"},
    "strip": {"on_off", "brightness", "color"},
    "candle": {"on_off"},
    # 전원류
    "plug": {"on_off", "energy"},
    "switch": {"on_off"},
    # 센서류 (읽기 전용)
    "motion": {"occupancy"},
    "temperature": {"temperature"},
    "humidity": {"humidity"},
    "contact": {"contact"},
    # 허브/확장
    "hub": set(),
    "thermostat": {"on_off", "target_temp"},
    "fan": {"on_off", "speed"},
    "curtain": {"position"},
    "lock": {"lock"},
    "camera": {"stream"},
}

# 읽기 전용 capability — control_device 대상에서 제외
_READ_ONLY_CAPABILITIES: set[str] = {
    "occupancy",
    "temperature",
    "humidity",
    "contact",
    "energy",
    "stream",
}

# 자연어 지칭 → device_type 후보 (§8-3 이름 매칭 5단계)
TYPE_ALIASES: dict[str, set[str]] = {
    "불": {"light", "lamp"},
    "조명": {"light", "lamp", "strip"},
    "전등": {"light"},
    "스탠드": {"lamp"},
    "무드등": {"strip", "candle"},
    "플러그": {"plug"},
    "콘센트": {"plug"},
    "스위치": {"switch"},
    "선풍기": {"fan"},
    "커튼": {"curtain"},
    "보일러": {"thermostat"},
}


def is_known_type(device_type: str) -> bool:
    return device_type in DEVICE_TYPES


def default_capabilities(device_type: str) -> set[str]:
    return set(DEVICE_TYPES.get(device_type, set()))


def writable_capabilities() -> list[str]:
    """제어 가능한 capability 전체 — control_device enum 동적 생성용 (§7-2)."""
    all_caps: set[str] = set()
    for caps in DEVICE_TYPES.values():
        all_caps |= caps
    return sorted(all_caps - _READ_ONLY_CAPABILITIES)


def types_for_alias(word: str) -> set[str]:
    return TYPE_ALIASES.get(word, set())
