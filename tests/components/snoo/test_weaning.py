"""Test bundled SNOO weaning mode behavior."""

import copy
from unittest.mock import AsyncMock

import pytest
from python_snoo.containers import SnooLevels, SnooStates

from homeassistant.components.snoo.weaning import WEANING_DEVICES_OPTION
from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import async_init_integration, find_update_callback
from .const import MOCK_SNOO_DATA

WEANING_SWITCH = "switch.test_snoo_emulated_weaning_mode"


async def test_enable_weaning_at_baseline(
    hass: HomeAssistant, bypass_api: AsyncMock
) -> None:
    """Apply motion-free baseline when enabled and restore normal baseline off."""
    entry = await async_init_integration(hass)
    data = copy.deepcopy(MOCK_SNOO_DATA)
    data.state_machine.state = SnooStates.baseline
    data.state_machine.level = SnooLevels.baseline
    data.state_machine.is_active_session = True
    update = find_update_callback(bypass_api, "random_num")
    update(data)
    await hass.async_block_till_done()
    assert hass.states.get(WEANING_SWITCH).state == STATE_OFF

    await hass.services.async_call(
        "switch", SERVICE_TURN_ON, {"entity_id": WEANING_SWITCH}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(WEANING_SWITCH).state == STATE_ON
    assert entry.options[WEANING_DEVICES_OPTION] == ["random_num"]
    bypass_api.set_level.assert_awaited_once_with(
        bypass_api.get_devices.return_value[0], SnooStates.weaning_baseline
    )

    data.state_machine.state = SnooStates.weaning_baseline
    update(data)
    await hass.async_block_till_done()
    bypass_api.set_level.reset_mock()
    await hass.services.async_call(
        "switch", SERVICE_TURN_OFF, {"entity_id": WEANING_SWITCH}, blocking=True
    )
    assert hass.states.get(WEANING_SWITCH).state == STATE_OFF
    assert entry.options[WEANING_DEVICES_OPTION] == []
    bypass_api.set_level.assert_awaited_once_with(
        bypass_api.get_devices.return_value[0], SnooStates.baseline
    )


@pytest.mark.parametrize(
    "state",
    [
        SnooStates.stop,
        SnooStates.level1,
        SnooStates.level2,
        SnooStates.level3,
        SnooStates.level4,
        SnooStates.timeout,
        SnooStates.pretimeout,
    ],
)
async def test_weaning_does_not_override_other_states(
    hass: HomeAssistant, bypass_api: AsyncMock, state: SnooStates
) -> None:
    """Do not start a stopped session or interrupt native soothing and timeout."""
    await async_init_integration(hass)
    data = copy.deepcopy(MOCK_SNOO_DATA)
    data.state_machine.state = state
    data.state_machine.is_active_session = True
    find_update_callback(bypass_api, "random_num")(data)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "switch", SERVICE_TURN_ON, {"entity_id": WEANING_SWITCH}, blocking=True
    )
    await hass.async_block_till_done()
    bypass_api.set_level.assert_not_awaited()


async def test_weaning_cancels_when_soothing_starts(
    hass: HomeAssistant, bypass_api: AsyncMock
) -> None:
    """Cancel a pending baseline command when the device starts soothing."""
    entry = await async_init_integration(hass)
    data = copy.deepcopy(MOCK_SNOO_DATA)
    data.state_machine.state = SnooStates.baseline
    data.state_machine.is_active_session = True
    update = find_update_callback(bypass_api, "random_num")
    update(data)
    await entry.runtime_data["random_num"].async_set_weaning_enabled(True)
    data = copy.deepcopy(data)
    data.state_machine.state = SnooStates.level1
    update(data)
    await hass.async_block_till_done()
    bypass_api.set_level.assert_not_awaited()


async def test_weaning_survives_reload(
    hass: HomeAssistant, bypass_api: AsyncMock
) -> None:
    """Restore the per-device mode from entry options without starting SNOO."""
    entry = await async_init_integration(hass)
    await entry.runtime_data["random_num"].async_set_weaning_enabled(True)
    bypass_api.start_subscribe.reset_mock()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    find_update_callback(bypass_api, "random_num")(MOCK_SNOO_DATA)
    await hass.async_block_till_done()
    assert hass.states.get(WEANING_SWITCH).state == STATE_ON
    bypass_api.set_level.assert_not_awaited()
