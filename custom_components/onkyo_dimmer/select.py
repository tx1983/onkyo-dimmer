import asyncio
import logging
from datetime import timedelta

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import event as event_helper
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

ONKYO_DOMAIN = "onkyo"
WATCH_INTERVAL = timedelta(seconds=10)
WRITE_TIMEOUT = 5

# Проверено на VSX-LX505: 00-03 поддерживаются, 08 даёт N/A
CODE_TO_NAME = {
    "00": "bright",
    "01": "dim",
    "02": "dark",
    "03": "off",
}
NAME_TO_CODE = {v: k for k, v in CODE_TO_NAME.items()}


class DimInstruction:
    """Инструкция DIM в формате, который понимает ReceiverManager.write()."""

    def __init__(self, parameter: bytes) -> None:
        self.raw_code = b"DIM"
        self.parameter = parameter

    @property
    def raw(self) -> bytes:
        return self.raw_code + self.parameter

    def __repr__(self) -> str:
        return f"DimInstruction({self.raw!r})"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    async_add_entities([OnkyoDimmerSelect(hass)])


class OnkyoDimmerSelect(SelectEntity, RestoreEntity):
    _attr_name = "Onkyo Display Dimmer"
    _attr_icon = "mdi:brightness-6"
    _attr_should_poll = False
    _attr_options = list(NAME_TO_CODE)

    def __init__(self, hass) -> None:
        self.hass = hass
        self._attr_unique_id = "onkyo_dimmer_display"
        self._attr_current_option = None
        self._manager = None
        self._was_available = False

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last and last.state in self._attr_options:
            self._attr_current_option = last.state
        unsub = event_helper.async_track_time_interval(
            self.hass, self._tick, WATCH_INTERVAL
        )
        self.async_on_remove(unsub)
        # Первый тик откладываем: внутри async_added_to_hass сущность ещё
        # в состоянии ADDING и async_write_ha_state() будет молча выброшен
        event_helper.async_call_later(self.hass, 0, self._tick)

    async def async_will_remove_from_hass(self) -> None:
        self._unregister()

    # --- связь с менеджером родной интеграции ---

    def _get_manager(self):
        for entry in self.hass.config_entries.async_entries(ONKYO_DOMAIN):
            data = getattr(entry, "runtime_data", None)
            if data is None:
                continue
            # runtime_data может быть OnkyoData(manager=...) или самим ReceiverManager
            manager = getattr(data, "manager", data)
            if hasattr(manager, "callbacks") and hasattr(manager, "connected"):
                return manager
        return None

    async def _tick(self, _now=None) -> None:
        try:
            manager = self._get_manager()
            if manager is not self._manager:
                self._unregister()
                if manager is not None:
                    self._register(manager)
                self._manager = manager
                _LOGGER.debug(
                    "manager changed: %r connected=%r",
                    manager,
                    getattr(manager, "connected", None),
                )
                self._was_available = False

            now = self.available
            self.async_write_ha_state()

            if now and not self._was_available:
                await self._query()
            self._was_available = now
        except Exception:
            _LOGGER.exception("onkyo dimmer tick failed")

    def _register(self, manager) -> None:
        cbs = manager.callbacks
        cbs.connect.append(self._on_connect)
        cbs.disconnect.append(self._on_disconnect)
        cbs.update.append(self._on_update)

    def _unregister(self) -> None:
        if self._manager is None:
            return
        cbs = self._manager.callbacks
        for lst, fn in (
            (cbs.connect, self._on_connect),
            (cbs.disconnect, self._on_disconnect),
            (cbs.update, self._on_update),
        ):
            try:
                lst.remove(fn)
            except ValueError:
                pass
        self._manager = None

    async def _query(self) -> None:
        if self._manager is None:
            return
        try:
            async with asyncio.timeout(WRITE_TIMEOUT):
                await self._manager.write(DimInstruction(b"QSTN"))
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Dimmer query failed: %r", err)

    async def _on_connect(self, _reconnect: bool) -> None:
        _LOGGER.debug("receiver connected")
        await self._query()
        self.async_write_ha_state()

    async def _on_disconnect(self) -> None:
        _LOGGER.debug("receiver disconnected")
        self.async_write_ha_state()

    async def _on_update(self, message) -> None:
        raw = getattr(message, "raw", None)
        if not isinstance(raw, (bytes, bytearray)) or not raw.startswith(b"DIM"):
            return
        _LOGGER.debug("RX: %r", raw)
        value = bytes(raw[3:5]).decode(errors="ignore")
        option = CODE_TO_NAME.get(value)
        if option is None:
            _LOGGER.debug("Unhandled DIM value: %r", raw)
            return
        if option != self._attr_current_option:
            self._attr_current_option = option
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._manager is not None and self._manager.connected

    # --- управление ---

    async def async_select_option(self, option: str) -> None:
        if self._manager is None:
            raise HomeAssistantError("Onkyo integration is not loaded")
        code = NAME_TO_CODE[option]
        try:
            async with asyncio.timeout(WRITE_TIMEOUT):
                await self._manager.write(DimInstruction(code.encode()))
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Failed to send DIM%s", code)
            raise HomeAssistantError(f"Failed to set dimmer: {err!r}") from err
        self._attr_current_option = option
        self.async_write_ha_state()