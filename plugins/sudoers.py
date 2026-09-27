from command import addsudo_cmd, delsudo_cmd, sudolist_cmd
from helpers import CMD

__MODULES__ = "Sudoers"
__HELP__ = """<blockquote>Command Help **Sudoers**</blockquote>
<blockquote>**Add delete sudo**</blockquote>
    **Add user to sudo user**
        `{0}addsudo` (username/reply user)
    **Remove user from sudo user**
        `{0}delsudo` (username/reply user)

<blockquote>**View sudolist**</blockquote>
    **Get all user from sudo user**
        `{0}sudolist`
        
<blockquote>**Delete all sudo**</blockquote>
    **You can delete all user from sudo user with this command**
        `{0}delsudo all`
<b>~    {1}</b>
"""


@CMD.UBOT("addsudo")
async def _(client, message):
    return await addsudo_cmd(client, message)


@CMD.UBOT("delsudo")
async def _(client, message):
    return await delsudo_cmd(client, message)


@CMD.UBOT("sudolist|listsudo")
async def _(client, message):
    return await sudolist_cmd(client, message)
