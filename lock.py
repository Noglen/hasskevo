from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from homeassistant.components.lock import LockEntity, PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    STATE_LOCKED,
    STATE_UNLOCKED,
)
from .const import DOMAIN

from .pykevo import Kevo

# PLATFORMS = ["lock"]

import logging
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    #     """Set up entry."""
    kevo = Kevo(config_entry.data["username"], config_entry.data["password"])

    lock = await KevoLock.FromLockID(kevo, config_entry.data["lockID"])

    kevo.ConnectWebSocket()

    async_add_devices([lock])

    return True


class KevoLock(LockEntity):

    states = {1: STATE_LOCKED, 2: STATE_UNLOCKED}

    def __init__(self, kevo, lockDetails):
        """Initialize the sensor."""
        self._state = lockDetails["bolt_state"]
        self._kevo = kevo
        self._name = lockDetails["name"]
        self._lockID = lockDetails["id"]
        self._manufacturername = lockDetails["brand"]
        self._swversion = lockDetails["firmware_version"]

    @staticmethod
    async def FromLockID(kevo, lockID):
        lockDetails = await kevo.GetLock(lockID)
        lock = KevoLock(kevo, lockDetails)
        return lock

    async def async_added_to_hass(self):
        self._kevo.Register_callback(self.state_changed)

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._lockID)
            },
            "name": self.name,
            "manufacturer": self._manufacturername,
            "sw_version": self._swversion,
        }

    @property
    def name(self):
        """Return the display name of this lock."""
        return self._name

    @property
    def should_poll(self):
        return False

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state == STATE_LOCKED

    def state_changed(self, newState):
        self._state = self.states[newState["messageData"]["boltState"]]
        self.async_write_ha_state()

    async def async_lock(self, **kwargs):
        """Instruct the lock to lock."""
        await self._kevo.Lock(self._lockID)

    async def async_unlock(self, **kwargs):
        """Instruct the lock to unlock."""
        await self._kevo.Unlock(self._lockID)

    # async def async_update(self):
    #     """Fetch new state data for this lock.
    #     This is the only method that should fetch new data for Home Assistant.
    #     """
    #     self._state = STATE_UNLOCKED
