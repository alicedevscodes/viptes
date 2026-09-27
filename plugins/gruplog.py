from clients import navy
from command import (ADD_ME, DELETED, EDITED, KICK_ME, LOGS_GROUP, REPLY,
                     logs_cmd)
from helpers import CMD

__MODULES__ = "Logs"

__HELP__ = """<blockquote>Command Help **Logs**</blockquote>
<blockquote>**On off gruplogs**</blockquote>
    **Set your gruplog, if you set on, you will create gruplog and receive message from bot
    for incoming private message or tag in chat group**
        `{0}logs` (on/off)
<b>   {1}</b>
"""


@CMD.UBOT("logs")
async def _(client, message):
    return await logs_cmd(client, message)


@CMD.NO_CMD("LOGS_GROUP", navy)
async def _(client, message):
    return await LOGS_GROUP(client, message)


@CMD.NO_CMD("REPLY", navy)
@CMD.IS_LOG
async def _(client, message):
    return await REPLY(client, message)


@CMD.EDITED()
async def _(client, message):
    return await EDITED(client, message)


@CMD.NO_CMD("ADD_ME", navy)
async def _(client, message):
    return await ADD_ME(client, message)


@CMD.NO_CMD("KICK_ME", navy)
async def _(client, message):
    return await KICK_ME(client, message)


@CMD.DELETED()
async def _(client, messages):
    return await DELETED(client, messages)
