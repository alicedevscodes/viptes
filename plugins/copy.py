IS_PRO = True
__MODULES__ = "Copy"
__HELP__ = """<blockquote>Command Help **Copy**</blockquote>
<blockquote>**Get messages with count**</blockquote>
    **This command can steal or get message media only with message count**
        `{0}copyall` or `{0}copyall2` (url) (count)

**Note**: For command `{0}copyall` only support media.
<b>   {1}</b>
"""


from command import copyall2_cmd, copyall_cmd
from helpers import CMD


@CMD.UBOT("copyall")
async def _(client, message):
    return await copyall_cmd(client, message)


@CMD.UBOT("copyall2")
async def _(client, message):
    return await copyall2_cmd(client, message)
