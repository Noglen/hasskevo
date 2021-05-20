"""Test Kevo hub."""
from bs4 import BeautifulSoup

import websockets
import json
import asyncio
import aiohttp


class KevoError(Exception):
    """Base exception for all Kevo errors"""

    pass


class Kevo(object):
    """
    Common mykevo.com operations
    """

    KEVO_URL_BASE = "https://www.mykevo.com"
    COMMANDS_URL_BASE = KEVO_URL_BASE + "/user/remote_locks/command"

    START_URL = KEVO_URL_BASE + "/login"
    LOGIN_URL = KEVO_URL_BASE + "/signin"
    AUTH_URL = KEVO_URL_BASE + "/user/remote_locks/auth/show.json"

    _loop = asyncio.get_event_loop()
    _callbacks = set()

    def __init__(self, username, password):
        self._username = username
        self._password = password
        self.session = None

    async def GetCsrfToken(self):
        """
        Get a mykevo.com crsf token

        Returns:
            A csrf token (str)
        """
        token = None

        async with self.session.get(Kevo.START_URL) as result:
            page = await result.text()
            login_page = BeautifulSoup(page, "html.parser")
            for field in login_page.find_all("input"):
                if field.get("name") == "authenticity_token":
                    token = field.get("value")
                    break
            if not token:
                raise KevoError("Could not find auth token on signin page")

            Kevo.token = token
            return token

    async def Login(self):
        """
        Create a http session and login to mykevo.com
        """
        self.session = aiohttp.ClientSession()
        token = await self.GetCsrfToken()
        login_payload = {
            "user[username]": self._username,
            "user[password]": self._password,
            "authenticity_token": token,
        }
        async with self.session.post(Kevo.LOGIN_URL, data=login_payload) as result:
            await result.text()

    async def _authGet(self, url):
        """
        Perform an HTTP get to the url, and login if required

        Args:
            url: The url to perform the get request against

        Returns:
            A csrf token (str)
        """
        if self.session == None:
            result = await self._authLoginGet(url)

        else:
            async with self.session.get(url) as resp:
                if resp.status == 500:
                    result = await self._authLoginGet(url)

                result = await resp.json()

        return result

    async def _authLoginGet(self, url):
        """
        Login and perform an HTTP GET to the url specified

        Args:
            url: The url to perform the get request against

        Returns:
            A csrf token (str)
        """
        await self.Login()

        async with self.session.get(url) as resp:
            if resp.status == 500:
                raise KevoError(
                    "Unable to connect to kevo api: {}".format(await resp.text())
                )

            result = await resp.json()

            return result

    async def GetLock(self, lockID):
        """
        Gets details for a lock

        Args:
            lockID: The url to perform the get request against

        Returns:
            A csrf token (str)
        """
        lock_detail_url = Kevo.COMMANDS_URL_BASE + "/lock.json?arguments={}".format(
            lockID
        )
        lock_details = await self._authGet(lock_detail_url)

        return lock_details

    def Register_callback(self, callback):
        """Register callback, called when lock changes state."""
        self._callbacks.add(callback)

    def Remove_callback(self, callback):
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    def ConnectWebSocket(self):
        """Starts a task with a loop for the websocket connection"""
        self._loop.create_task(self._getStatusLoop())

    async def _getWsUrl(self):
        auth_details = await self._authGet(Kevo.AUTH_URL)

        wsurl = auth_details["socket_location"]

        return wsurl

    async def _getStatusLoop(self):

        wsurl = await self._getWsUrl()

        async with websockets.connect(wsurl) as websocket:
            while True:
                try:
                    text = await websocket.recv()
                except websockets.ConnectionClosed as e:
                    if e.code == 1000:
                        break
                        # TODO: handle restarting the connection
                    else:
                        raise e
                for callback in self._callbacks:
                    callback(json.loads(text))

    async def Lock(self, lockID):
        """
        Lock this lock.  If the lock is already locked, this method has no effect.
        """
        command_url = Kevo.COMMANDS_URL_BASE + "/remote_lock.json?arguments={}".format(
            lockID
        )
        await self._authGet(command_url)

    async def Unlock(self, lockID):
        """
        Unlock this lock.  If the lock is already unlocked, this method has no effect.
        """
        command_url = (
            Kevo.COMMANDS_URL_BASE + "/remote_unlock.json?arguments={}".format(lockID)
        )
        await self._authGet(command_url)
