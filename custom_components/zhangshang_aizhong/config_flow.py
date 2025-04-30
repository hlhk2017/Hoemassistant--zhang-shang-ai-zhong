import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_AUTHENTICATION, CONF_TOKEN
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZhangshangAizhongConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            phone = user_input["phone"]
            password = user_input["password"]
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="掌上爱众",
                data={
                    "phone": phone,
                    "password": password
                }
            )

        data_schema = vol.Schema({
            vol.Required("phone"): str,
            vol.Required("password"): str
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )
    
