"""Apply motion-free baseline without interfering with native soothing."""

import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import Any

from python_snoo.containers import SnooData, SnooDevice, SnooStates
from python_snoo.exceptions import SnooCommandException
from python_snoo.snoo import Snoo

_LOGGER = logging.getLogger(__name__)
WEANING_DEVICES_OPTION = "emulated_weaning_devices"


class WeaningController:
    """Debounce baseline transitions and leave other device states alone."""

    def __init__(
        self,
        snoo: Snoo,
        device: SnooDevice,
        create_task: Callable[[Coroutine[Any, Any, None]], asyncio.Task],
        enabled: bool = False,
    ) -> None:
        """Initialize device commands and the restored mode setting."""
        self.snoo = snoo
        self.device = device
        self.create_task = create_task
        self.enabled = enabled
        self.data: SnooData | None = None
        self._task: asyncio.Task | None = None

    def should_apply(self) -> bool:
        """Only an active, unlocked ordinary baseline is eligible."""
        return (
            self.enabled
            and self.data is not None
            and self.data.state_machine.is_active_session
            and self.data.state_machine.state == SnooStates.baseline
            and self.data.state_machine.hold == "off"
        )

    def update(self, data: SnooData) -> None:
        """Schedule at most one command, cancelling stale baseline timers."""
        self.data = data
        if not self.should_apply():
            self.cancel()
        elif self._task is None or self._task.done():
            self._task = self.create_task(self._apply_after_delay())

    def cancel(self) -> None:
        """Cancel a pending transition when disabled or leaving baseline."""
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _apply_after_delay(self) -> None:
        """Recheck the latest device state immediately before commanding it."""
        await asyncio.sleep(2)
        if self.should_apply():
            try:
                await self.snoo.set_level(self.device, SnooStates.weaning_baseline)
            except SnooCommandException:
                _LOGGER.exception("Unable to apply emulated weaning baseline")

    async def set_enabled(self, enabled: bool) -> None:
        """Enable baseline automation or restore unlocked normal baseline."""
        self.enabled = enabled
        self.cancel()
        if enabled:
            if self.data is not None:
                self.update(self.data)
        elif (
            self.data is not None
            and self.data.state_machine.is_active_session
            and self.data.state_machine.state == SnooStates.weaning_baseline
            and self.data.state_machine.hold == "off"
        ):
            await self.snoo.set_level(self.device, SnooStates.baseline)
