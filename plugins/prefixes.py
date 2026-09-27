from command import setprefix_cmd
from helpers import CMD

__MODULES__ = "Prefix"
__HELP__ = """<blockquote>Command Help **Prefix**</blockquote>
<blockquote>**Set handler userbot**</blockquote>
    **You can set handler or trigger to your userbot**
        `{0}setprefix` (trigger/symbol)
<b>   {1}</b>
"""
IS_PRO = True


@CMD.UBOT("setprefix")
async def _(client, message):
    return await setprefix_cmd(client, message)
