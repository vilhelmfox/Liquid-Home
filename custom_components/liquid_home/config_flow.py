"""Liquid Home configuration through the Home Assistant user interface."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "liquid_home"


class LiquidHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Install Liquid Home and choose a pairing code."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            pin = str(user_input.get("pairing_pin", ""))
            if len(pin) < 12:
                errors["pairing_pin"] = "pin_too_short"
            else:
                return self.async_create_entry(
                    title="Liquid Home", data={"pairing_pin": pin}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("pairing_pin"): str}),
            errors=errors,
        )
