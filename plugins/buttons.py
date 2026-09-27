from command import button_cmd, buttonch_cmd
from helpers import CMD

__MODULES__ = "Button"
__HELP__ = """<blockquote>Command Help **Button** </blockquote>
<blockquote>**Make button from text**</blockquote>
    **You can create buttons from the text, please read markdown format**
        `{0}button` (reply text)
<b>   {1}</b>
"""


@CMD.UBOT("buttonch")
async def _(client, message):
    return await buttonch_cmd(client, message)


@CMD.UBOT("button")
async def _(client, message):
    return await button_cmd(client, message)
