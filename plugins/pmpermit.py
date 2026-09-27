from clients import navy
from command import AUTO_APPROVE, PMPERMIT, nopm_cmd, okpm_cmd, pmpermit_cmd
from helpers import CMD

__MODULES__ = "PMPermit"
__HELP__ = """<blockquote>Command Help **PMPermit** </blockquote>
<blockquote>**On off pmpermit**</blockquote>
    **Set to on pmpermit**
        `{0}pmpermit set on`
    **Set to off pmpermit**
        `{0}pmpermit set off`

<blockquote>**Set media pmpermit**</blockquote>
    **You can set media to your pmpermit, media can be set photo, video**
        `{0}pmpermit media` (reply media)

<blockquote>**Set text pmpermit**</blockquote>
    **You can change costum text to your pmpermit message**
        `{0}pmpermit teks` (text/reply text)

<blockquote>**Set warn pmpermit**</blockquote>
    **You can set warning pmpermit for incoming message**
        `{0}pmpermit warn` (number) or 10

<blockquote>**Get status pmpermit**</blockquote>
    **For this command, you can get status, text, warn, and media from pmpermit or you can see example below**
        `{0}pmpermit get` (query)

<blockquote>**Approve disapprove user**</blockquote>
    **This command for approve user message**
        `{0}ok`
    **This command for disapprove user message**
        `{0}no`

<blockquote>**Disapprove user/all**</blockquote>
        `{0}ok`
    **Delete user from approved database**
        `{0}pmpermit disapproved @username`
    **Delete all user from approved database**
        `{0}pmpermit disapproved all`
    
<blockquote>**Example:**
    `{0}pmpermit get status`
    `{0}pmpermit get teks`
    `{0}pmpermit get warn`
    `{0}pmpermit get approved`
    `{0}pmpermit get media`</blockquote>
<b>   {1}</b>
"""


@CMD.UBOT("pmpermit")
async def _(client, message):
    return await pmpermit_cmd(client, message)


@CMD.UBOT("ok")
@CMD.ONLY_PRIVATE
async def _(client, message):
    return await okpm_cmd(client, message)


@CMD.UBOT("no")
@CMD.ONLY_PRIVATE
async def _(client, message):
    return await nopm_cmd(client, message)


@CMD.NO_CMD("PMPERMIT", navy)
@CMD.capture_err
async def _(client, message):
    return await PMPERMIT(client, message)


@CMD.NO_CMD("AUTO_APPROVE", navy)
@CMD.capture_err
async def _(client, message):
    return await AUTO_APPROVE(client, message)
