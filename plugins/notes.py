from command import clearnotes_cmd, getnote_cmd, listnotes_cmd, savenote_cmd
from helpers import CMD

__MODULES__ = "Notes"
__HELP__ = """<blockquote>Command Help **Notes**</blockquote>
<blockquote>**Save the notes** </blockquote>
    **You can save message with this command**
        `{0}save` (note name) (reply message)

<blockquote>**Get the notes** </blockquote>
    **Get saved message you are**
        `{0}get` (note name)

<blockquote>**List the notes** </blockquote>
    **View all saved note**
        `{0}notes`

<blockquote>**Clear the notes**</blockquote> 
    **You can clear or delete the one note or many note**
        `{0}clear` (note name) or (name1, name2, name2)

<blockquote>**Clear all notes**</blockquote>
    **For this command you can delete all saved note**
        `{0}clear all`
<b>   {1}</b>
"""


@CMD.UBOT("save")
async def _(client, message):
    return await savenote_cmd(client, message)


@CMD.UBOT("get")
async def _(client, message):
    return await getnote_cmd(client, message)


@CMD.UBOT("notes")
async def _(client, message):
    return await listnotes_cmd(client, message)


@CMD.UBOT("clear")
async def _(client, message):
    return await clearnotes_cmd(client, message)
