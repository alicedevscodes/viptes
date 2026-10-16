from pyrogram.types import InlineKeyboardMarkup

from clients import alice
from config import BOT_NAME, HELPABLE, USENAME_OWNER
from database import dB
from helpers import paginate_modules


async def basic_plugins(client, message):
    user_id = message.from_user.id
    if await dB.get_var(message.from_user.id, "is_bot_pro"):
        await dB.remove_var(message.from_user.id, "is_bot_pro")
    is_pro = False
    visible_helpable = {
        name: data for name, data in HELPABLE.items() if is_pro or not data["is_pro"]
    }
    prefix = alice.get_prefix(user_id)
    text_help = (
        await dB.get_var(user_id, "text_help")
        or f"**🤖 {BOT_NAME} by {USENAME_OWNER}**"
    )
    full = f"<a href=tg://user?id={message.from_user.id}>{message.from_user.first_name} {message.from_user.last_name or '' }</a>"
    msg = """<b>
Inline Help 
    Prefixes: <code>{}</code>
    Plugins: <code>{}</code>
    {} </b>
<blockquote>{}</blockquote>""".format(
        " ".join(prefix), len(visible_helpable), full, text_help
    )
    await dB.set_var(user_id, "is_bot", True)
    return await message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(
            paginate_modules(0, visible_helpable, "help", is_bot=True)
        ),
    )


async def pro_plugins(client, message):
    user_id = message.from_user.id
    prefix = alice.get_prefix(user_id)
    text_help = (
        await dB.get_var(user_id, "text_help")
        or f"**🤖 {BOT_NAME} by {USENAME_OWNER}**"
    )
    full = f"<a href=tg://user?id={message.from_user.id}>{message.from_user.first_name} {message.from_user.last_name or '' }</a>"
    msg = """<b>
Inline Help 
    Prefixes: <code>{}</code>
    Plugins: <code>{}</code>
    {} </b>
<blockquote>{}</blockquote>""".format(
        " ".join(prefix), len(HELPABLE), full, text_help
    )
    await dB.set_var(user_id, "is_bot", True)
    await dB.set_var(user_id, "is_bot_pro", True)
    return await message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(
            paginate_modules(0, HELPABLE, "help", is_bot=True)
        ),
    )
