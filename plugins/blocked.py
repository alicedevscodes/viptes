__MODULES__ = "Blocked"
__HELP__ = """<blockquote>Command Help **Blocked**</blockquote>
<blockquote>**Basic commands**</blockquote>
    **Unblock all users**
        `{0}unblockall`
    **Get blocked users**
        `{0}blocked`
<b>   {1}</b>
"""


from command import blocked_cmd
from helpers import CMD


@CMD.UBOT("unblockall|blocked")
async def _(client, message):
    return await blocked_cmd(client, message)
