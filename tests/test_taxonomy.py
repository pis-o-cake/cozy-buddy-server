from app.domain.device import taxonomy


def test_writable_capabilities_exclude_read_only():
    caps = taxonomy.writable_capabilities()
    assert "on_off" in caps
    assert "brightness" in caps
    assert "target_temp" in caps  # thermostat — §7-2 enum 확장 검증
    assert "lock" in caps
    # 읽기 전용은 제어 대상에서 제외
    for read_only in ("temperature", "humidity", "occupancy", "energy", "stream"):
        assert read_only not in caps


def test_default_capabilities_from_type():
    assert taxonomy.default_capabilities("light") == {"on_off", "brightness", "color_temp"}
    assert taxonomy.default_capabilities("unknown-type") == set()


def test_type_aliases():
    assert taxonomy.types_for_alias("불") == {"light", "lamp"}
    assert taxonomy.types_for_alias("없는말") == set()
