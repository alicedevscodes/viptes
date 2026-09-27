from command import ignore_cmd
from helpers import CMD

__MODULES__ = "Ignore"
__HELP__ = """<blockquote>Command Help **Ignore**</blockquote>
<blockquote>**Enable plugins**</blockquote>
    **You can disable plugins if you want**
        `{0}ignore` (name plugins)

<blockquote>**Disable plugins**</blockquote>     **You can enable plugins if you want**
        `{0}reignore` (name plugins)

<blockquote>**View disabled plugins**</blockquote>     **You can view disabled plugins**
        `{0}ignored`
<b>   {1}</b>
"""


@CMD.UBOT("ignore|reignore|ignored")
async def _(client, message):
    return await ignore_cmd(client, message)
