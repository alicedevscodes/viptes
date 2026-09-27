from command import setemoji_cmd
from helpers import CMD

__MODULES__ = "Emoji"
__HELP__ = """<blockquote>Command Help **Emoji**</blockquote>
<blockquote>**Set emoji ping**</blockquote>
    **You can set ping emoji with this command**
        `{0}setemoji ping` (emoji)

<blockquote>**Set emoji uptime**</blockquote>
    **You can set uptime emoji with this command**
        `{0}setemoji uptime` (emoji)

<blockquote>**Set emoji profil**</blockquote>
    **You can set profile emoji with this command**
        `{0}setemoji profil` (emoji)

<blockquote>**Set emoji robot**</blockquote>
    **You can set robot emoji with this command**
        `{0}setemoji robot` (emoji)

<blockquote>**Set emoji msg**</blockquote>
    **You can set msg emoji with this command**
        `{0}setemoji msg` (emoji)

<blockquote>**Set emoji warn**</blockquote>
    **You can set warn emoji with this command**
        `{0}setemoji warn` (emoji)

<blockquote>**Set emoji block**</blockquote>
    **You can set block emoji with this command**
        `{0}setemoji block` (emoji)

<blockquote>**Set emoji gagal**</blockquote>
    **You can set gagal emoji with this command**
        `{0}setemoji gagal` (emoji)

<blockquote>**Set emoji sukses**</blockquote>
    **You can set sukses emoji with this command**
        `{0}setemoji sukses` (emoji)

<blockquote>**Set emoji owner**</blockquote>
    **You can set owner emoji with this command**
        `{0}setemoji owner` (emoji)

<blockquote>**Set emoji klip**</blockquote>
    **You can set klip emoji with this command**
        `{0}setemoji klip` (emoji)

<blockquote>**Set emoji net**</blockquote>
    **You can set net emoji with this command**
        `{0}setemoji net` (emoji)

<blockquote>**Set emoji up**</blockquote>
    **You can set up emoji with this command**
        `{0}setemoji up` (emoji)

<blockquote>**Set emoji down**</blockquote>
    **You can set down emoji with this command**
        `{0}setemoji down` (emoji)

<blockquote>**Set emoji speed**</blockquote>
    **You can set speed emoji with this command**
        `{0}setemoji speed` (emoji)

<blockquote>**Set emoji proses**</blockquote>
    **You can set proses emoji with this command**
        `{0}setemoji proses` (emoji)

<blockquote>**Set emoji status**</blockquote>
    **You can set status emoji with this command**
        `{0}setemoji status` (emoji)

<blockquote>**Get id from message**</blockquote>
    **You can set id emoji or media with this command**
        `{0}id` (reply message)

<blockquote>**Get status emoji**</blockquote>
    **Get all youre emoji set**
        `{0}getemoji`
    
<blockquote>**Note**: Emoji only working on premium users.</blockquote>
<b>   {1}</b>
"""


@CMD.UBOT("setemoji|getemoji")
async def _(client, message):
    return await setemoji_cmd(client, message)
