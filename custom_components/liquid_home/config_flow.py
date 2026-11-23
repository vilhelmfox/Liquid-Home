"""User interface setup for Liquid Home; no YAML or user-created PIN."""
from __future__ import annotations

import secrets
import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "liquid_home"


class LiquidHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Generate a secure random pairing code during onboarding."""

    VERSION = 2

    def __init__(self):
        self._generated_pin = None

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if self._generated_pin is None:
            self._generated_pin = secrets.token_urlsafe(18)
        if user_input is not None:
            return self.async_create_entry(
                title="Liquid Home", data={"pairing_pin": self._generated_pin}
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={"pairing_code": self._generated_pin},
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return LiquidHomeOptionsFlow(config_entry)


class LiquidHomeOptionsFlow(config_entries.OptionsFlow):
    """Show or rotate the pairing code from the integration UI."""

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        current = self._entry.options.get(
            "pairing_pin", self._entry.data.get("pairing_pin", "")
        )
        if user_input is not None:
            if user_input.get("regenerate", False):
                current = secrets.token_urlsafe(18)
            return self.async_create_entry(
                title="", data={"pairing_pin": current}
            )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Optional("regenerate", default=False): bool}),
            description_placeholders={"pairing_code": current},
        )
