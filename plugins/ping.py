from command import absen_cmd, mping_cmd, settext_cmd
from helpers import CMD

__MODULES__ = "Settings"
__HELP__ = """<blockquote>Command Help **Settings**</blockquote>
<blockquote>**Set text ping message**</blockquote>
    **You can set costum text ping**
        `{0}set_text ping` (text/reply text)

<blockquote>**Set text uptime message**</blockquote>
    **You can set costum text uptime**
        `{0}set_text uptime` (text/reply text)

<blockquote>**Set text owner message**</blockquote>
    **You can set costum text owner**
        `{0}set_text owner` (text/reply text)

<blockquote>**Set text ubot message**</blockquote>
    **You can set costum text ubot**
        `{0}set_text ubot` (text/reply text)

<blockquote>**Set text sukses message**</blockquote>
    **You can set costum text sukses gcast**
        `{0}set_text sukses` (text/reply text)

<blockquote>**Set text proses message**</blockquote>
    **You can set costum text proses**
        `{0}set_text proses` (text/reply text)

<blockquote>**Set text help message**</blockquote>
    **You can set costum text inline help**
        `{0}set_text help` (text/reply text)

<blockquote>**Note:** Use `{0}ping` to check the changes and `{0}help`</blockquote>
<b>   {1}</b>
"""


@CMD.UBOT("set_text")
async def _(client, message):
    return await settext_cmd(client, message)


@CMD.UBOT("ping")
@CMD.DEV_CMD("mping")
@CMD.FAKEDEV("mping")
async def _(client, message):
    return await mping_cmd(client, message)


@CMD.FAKEDEV("absen")
@CMD.DEV_CMD("absen")
async def _(client, message):
    return await absen_cmd(client, message)
