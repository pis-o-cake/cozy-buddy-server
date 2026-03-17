"""Custom exception definitions."""


class CozyBuddyError(Exception):
    """Base exception class."""

    def __init__(self, message: str = "", code: str = "UNKNOWN_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


class DeviceError(CozyBuddyError):
    """IoT device exception."""

    def __init__(self, message: str = "", device_name: str = "") -> None:
        self.device_name = device_name
        super().__init__(message=message, code="DEVICE_ERROR")


class DeviceOfflineError(DeviceError):
    """Device offline exception."""

    def __init__(self, device_name: str = "") -> None:
        super().__init__(
            message=f"Device unreachable: {device_name}",
            device_name=device_name,
        )


class LLMError(CozyBuddyError):
    """LLM service exception."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message=message, code="LLM_ERROR")


class VoiceError(CozyBuddyError):
    """Voice service exception."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message=message, code="VOICE_ERROR")


class ScenarioError(CozyBuddyError):
    """Scenario exception."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message=message, code="SCENARIO_ERROR")
