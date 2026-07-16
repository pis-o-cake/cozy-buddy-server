import pytest

from app.core.exceptions import ProviderNotFoundError
from app.core.registry import ProviderRegistry


class _Dummy:
    def __init__(self, value: int = 0) -> None:
        self.value = value


def test_register_and_build():
    registry: ProviderRegistry[_Dummy] = ProviderRegistry("dummy")
    registry.register("a")(_Dummy)

    instance = registry.build("a", value=7)
    assert isinstance(instance, _Dummy)
    assert instance.value == 7
    assert registry.names() == ["a"]


def test_unknown_name_raises():
    registry: ProviderRegistry[_Dummy] = ProviderRegistry("dummy")
    with pytest.raises(ProviderNotFoundError):
        registry.build("nope")


def test_duplicate_registration_fails_fast():
    registry: ProviderRegistry[_Dummy] = ProviderRegistry("dummy")
    registry.register("a")(_Dummy)
    with pytest.raises(ValueError):
        registry.register("a")(_Dummy)
