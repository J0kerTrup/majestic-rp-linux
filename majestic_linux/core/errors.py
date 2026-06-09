class RunnerError(Exception):
    """Base class for clear user-facing runner errors."""


class ConfigError(RunnerError):
    """Configuration could not be loaded or parsed."""


class DetectionError(RunnerError):
    """Required installation paths could not be detected."""


class PatchError(RunnerError):
    """Launcher JavaScript patching failed."""


class CommandError(RunnerError):
    """External command failed."""
