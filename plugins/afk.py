from clients import navy
from helpers import AFK_, CMD

__MODULES__ = "AFK"
__HELP__ = """<blockquote>Command Help **AFK**</blockquote>
<blockquote>**Enabe afk mode**</blockquote>
    **You can set status to AFK mode**
        `{0}afk` (reason)
    
<blockquote>**Disable afk mode**</blockquote>
    **After AFK mode on, you can set to UNAFK mode**
        `{0}unafk`
<b>   {1}</b>
"""


@CMD.UBOT("afk")
async def _(client, message):
    return await AFK_.set_afk(client, message)


@CMD.NO_CMD("AFK", navy)
@CMD.capture_err
async def _(client, message):
    return await AFK_.get_afk(client, message)


@CMD.UBOT("unafk")
async def _(client, message):
    return await AFK_.unset_afk(client, message)
