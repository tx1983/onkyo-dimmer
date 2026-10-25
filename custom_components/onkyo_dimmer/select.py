import asyncio
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

ONKYO_DOMAIN = "onkyo"
WATCH_INTERVAL = 10

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
        self._task = None

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last and last.state in self._attr_options:
            self._attr_current_option = last.state
        self._task = self.hass.async_create_background_task(
            self._watch(), name="onkyo_dimmer_watch"
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._task:
            self._task.cancel()
        self._unregister()

    # --- связь с менеджером родной интеграции ---

    def _get_manager(self):
        for entry in self.hass.config_entries.async_entries(ONKYO_DOMAIN):
            data = getattr(entry, "runtime_data", None)
            if data is not None and getattr(data, "manager", None) is not None:
                return data.manager
        return None

    async def _watch(self) -> None:
        """Следим за менеджером (он пересоздаётся при перезагрузке интеграции)."""
        while True:
            manager = self._get_manager()
            if manager is not self._manager:
                self._unregister()
                self._manager = manager
                if manager is not None:
                    self._register()
                    if manager.connected:
                        await self._query()
                self.async_write_ha_state()
            await asyncio.sleep(WATCH_INTERVAL)

    def _register(self) -> None:
        cbs = self._manager.callbacks
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
            await self._manager.write(DimInstruction(b"QSTN"))
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Dimmer query failed: %r", err)

    async def _on_connect(self, _reconnect: bool) -> None:
        await self._query()
        self.async_write_ha_state()

    async def _on_disconnect(self) -> None:
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
            await self._manager.write(DimInstruction(code.encode()))
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Failed to send DIM%s", code)
            raise HomeAssistantError(f"Failed to set dimmer: {err!r}") from err
        self._attr_current_option = option
        self.async_write_ha_state()