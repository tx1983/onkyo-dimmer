import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

DOMAIN = "onkyo_dimmer"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass, config):
    hass.async_create_task(async_load_platform(hass, "select", DOMAIN, {}, config))
    return True