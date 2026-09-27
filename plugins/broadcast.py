from command import (addbcdb_cmd, addbl_cmd, bc_cmd, bcerror_cmd, cancel_cmd,
                     delbcdb_cmd, delbl_cmd, gcast_cmd, listbcdb_cmd,
                     listbl_cmd, sendinline_cmd, ucast_cmd)
from helpers import CMD

__MODULES__ = "Broadcast"
__HELP__ = """<blockquote>Command Help **Broadcast**</blockquote>
<blockquote>**Broadcast to db**</blockquote>
    **Send broadcast message to chats db**
        `{0}bc db` (text/reply text)

<blockquote>**Broadcast to group**</blockquote>
    **Send broadcast message to chats group**
        `{0}bc group` (text/reply text)

<blockquote>**Broadcast to all**</blockquote>
    **Send broadcast message to chats group and private**
        `{0}bc all` (text/reply text)

<blockquote>**Broadcast to users**</blockquote>
    **Send broadcast message to private chat**
        `{0}bc private` (text/reply text)

<blockquote>**Add blacklist chat**</blockquote>
    **Add chat to blacklist broadcast**
        `{0}addbl` (chatid)

<blockquote>**Delete blacklist chat**</blockquote>
    **Delete chat from blacklist broadcast**
        `{0}delbl` (chatid)

<blockquote>**List blacklist chat**</blockquote>
    **View all chat from blacklist broadcast**
        `{0}listbl`

<blockquote>**Add broadcast-db**</blockquote>    
    **Add chat to broadcast db**
        `{0}add-bcdb` (chatid)

<blockquote>**Delete broadcast-db**    </blockquote>
    **Delete chat to broadcast db**
        `{0}del-bcdb` (chatid)

<blockquote>**List broadcast-db**    </blockquote>
    **View all chats on broadcast db**
        `{0}list-bcdb`

<blockquote>**Cancel broadcast**</blockquote>
    **Cancel broadcast message, give taskid**
        `{0}cancel` (taskid)
<b>   {1}</b>
"""


@CMD.UBOT("bc")
@CMD.FAKEDEV("bc")
async def _(client, message):
    return await bc_cmd(client, message)


@CMD.UBOT("gcast")
@CMD.FAKEDEV("gcast")
async def _(client, message):
    return await gcast_cmd(client, message)


@CMD.UBOT("ucast")
@CMD.FAKEDEV("ucast")
async def _(client, message):
    return await ucast_cmd(client, message)


@CMD.UBOT("bc-error")
@CMD.FAKEDEV("bc-error")
async def _(client, message):
    return await bcerror_cmd(client, message)


@CMD.UBOT("cancel")
@CMD.FAKEDEV("cancel")
async def _(client, message):
    return await cancel_cmd(client, message)


@CMD.UBOT("addbl")
@CMD.DEV_CMD("addbl")
@CMD.FAKEDEV("addbl")
async def _(client, message):
    return await addbl_cmd(client, message)


@CMD.UBOT("delbl")
@CMD.DEV_CMD("delbl")
@CMD.FAKEDEV("delbl")
async def _(client, message):
    return await delbl_cmd(client, message)


@CMD.UBOT("listbl")
@CMD.FAKEDEV("listbl")
async def _(client, message):
    return await listbl_cmd(client, message)


@CMD.UBOT("add-bcdb")
async def _(client, message):
    return await addbcdb_cmd(client, message)


@CMD.UBOT("del-bcdb")
async def _(client, message):
    return await delbcdb_cmd(client, message)


@CMD.UBOT("list-bcdb")
async def _(client, message):
    return await listbcdb_cmd(client, message)


@CMD.UBOT("send")
async def _(client, message):
    return await sendinline_cmd(client, message)
