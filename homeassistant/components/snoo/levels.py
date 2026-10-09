"""Compatibility helpers for the pinned python-snoo library."""

from python_snoo.containers import SnooData, SnooLevels, SnooStates


def current_level(data: SnooData) -> SnooLevels | SnooStates | None:
    """Preserve motion-free baseline, which SnooLevels 0.8.3 lacks."""
    if data.state_machine.state == SnooStates.weaning_baseline:
        return SnooStates.weaning_baseline
    return data.state_machine.level


def current_option(data: SnooData) -> str | None:
    """Return the reported intensity, including motion-free baseline."""
    level = current_level(data)
    return level.name if level is not None else None


def command_level(option: str) -> SnooLevels | SnooStates:
    """Map weaning to the supported command-state enum."""
    if option == "weaning_baseline":
        return SnooStates.weaning_baseline
    return SnooLevels[option]


INTENSITY_OPTIONS = [
    "baseline",
    "weaning_baseline",
    "level1",
    "level2",
    "level3",
    "level4",
    "stop",
]
