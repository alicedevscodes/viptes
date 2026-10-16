import asyncio
import os
import re
import time
import traceback
from datetime import timedelta
from gc import get_objects

import requests
import wget

from pyrogram import enums, raw
from pyrogram.enums import ButtonStyle
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.helpers import ikb, cell, divider, paragraph, send_rich, table
from pyrogram.types import (
    InlineKeyboardMarkup, InputRichMessage,
    RichTextBold, RichTextCustomEmoji, RichTextTextMention, RichTextBold
)
from pyrogram.types import InlineKeyboardButton as Ikb
from pyrogram.types import (InlineKeyboardMarkup, InputMediaAnimation,
                            InputMediaAudio, InputMediaDocument,
                            InputMediaPhoto, InputMediaVideo)
from pyrogram.utils import unpack_inline_message_id
from pytz import timezone

from clients import bot, navy
from config import (API_BOTCHAX, API_MAELYN, BOT_NAME, COPY_ID, HELPABLE,
                    LOG_SELLER, SUDO_OWNERS, OWNER_ID, USENAME_OWNER)
from database import dB, state
from helpers import (ButtonUtils, Emoji, Message, TokenReferal, Tools,
                      animate_proses, gens_font, no_trigger,
                     paginate_modules, query_fonts)
from logs import logger


MESSAGE_DICT = {}
CONVERSATIONS = {}
SUPPORT = []

EMO = {
    "tulis": (5256143829672672750, "✍️"),
    "batal": (6253758805755038090, "❌"),
    "sukses": (6046412391887935443, "✅"),
    "gagal": (6253758805755038090, "⚠️"),
    "info": (5256143829672672750, "ℹ️"),
}



top_text = """
<b>Inline Help
    Prefixes: <code>{}</code>
    Plugins: <code>{}</code>
    {}</b>
<blockquote>{}</blockquote>"""

text_markdown = "**To view markdown format please click on the button below.**"
text_formatting = """
> **Markdown Formatting**
> Anda dapat memformat pesan Anda menggunakan **tebal**, _miring_, --garis bawah--, ~~coret~~, dan banyak lagi.
>
> `<code>kata kode</code>`: Tanda kutip terbalik digunakan buat font monospace. Ditampilkan sebagai: `kata kode`.
>
> `<i>miring</i>`: Garis bawah digunakan buat font miring. Ditampilkan sebagai: __kata miring__.
>
> `<b>tebal</b>`: Asterisk digunakan buat font tebal. Ditampilkan sebagai: **kata tebal**.
>
> `<u>garis bawah</u>`: Buat membuat teks --garis bawah--.
>
> `<strike>coret</strike>`: Tilda digunakan buat strikethrough. Ditampilkan sebagai: ~~coret~~.
>
> `<spoiler>spoiler</spoiler>`: Garis vertikal ganda digunakan buat spoiler. Ditampilkan sebagai: ||spoiler||.
>
> `[hyperlink](contoh)`: Ini adalah pemformatan yang digunakan buat hyperlink.
>
> `<blockquote>teks quote</blockquote>`: Ini adalah pemformatan untuk > teks quote >
>
> `Hallo Disini [Tombol 1|https://link.com]` : Ini adalah pemformatan yang digunakan membuat tombol.
> `Halo Disini [Tombol 1|t.me/kynansupport][Tombol 2|t.me/kontenfilm|same]` : Ini akan membuat tombol berdampingan.
>
> Anda juga bisa membuat tombol callback_data dengan diawal tanda `cb_`
> Jika ingin membuat copy text gunakan Halo Disini `[Click To Copy|copy:1234]`
> Contoh callback `Halo Disini [Tombol 1|data][Tombol 2|data|same]`

> Anda juga dapat membuat tombol callback answer dengan diawal tanda `alert:`
> Contoh callback answer`Halo Disini [Tombol 1|alert:Yang klik jelek][Tombol 2|alert:Jangan diklik\nTapi boong|same]`
"""

text_fillings = "<blockquote><b>Fillings</b>\n\nAnda juga dapat menyesuaikan isi pesan Anda dengan data kontekstual. Misalnya, Anda bisa menyebut nama pengguna dalam pesan selamat datang, atau menyebutnya dalam filter!\n\n<b>Isian yang didukung:</b>\n\n<code>{first}</code>: Nama depan pengguna.\n<code>{last}</code>: Nama belakang pengguna.\n<code>{fullname}</code>: Nama lengkap pengguna.\n<code>{username}</code>: Nama pengguna pengguna. Jika mereka tidak memiliki satu, akan menyebutkan pengguna tersebut.\n<code>{mention}</code>: Menyebutkan pengguna dengan nama depan mereka.\n<code>{id}</code>: ID pengguna.\n<code>{date}</code>: Tanggal, <code>{day}</code>: hari, <code>{month}</code>: bulan, <code>{year}</code>: tahun, <code>{hour}</code>: jam, <code>{minute}</code>: menit.</blockquote>"

def emo(emoji_id, alt="✨"):
    return RichTextCustomEmoji(custom_emoji_id=str(emoji_id), alternative_text=alt)


def _batalkan_ask(chat_id):
    """Hentikan listener bot.ask yang masih menunggu (nama method beda tiap versi pyromod)."""
    for name in ("cancel_listener", "stop_listening"):
        fn = getattr(bot, name, None)
        if not fn:
            continue
        try:
            fn(chat_id=chat_id)
            return True
        except Exception:
            continue
    return False


def _menu_awal(user_id):
    return ButtonUtils.start_menu(is_admin=user_id in SUDO_OWNERS)


async def kirim_rich(chat_id, jenis, teks, reply_markup=None):
    emoji_id, fallback = EMO[jenis]
    return await send_rich(
        bot,
        chat_id,
        LOG_SELLER,
        paragraph([emo(emoji_id, fallback), RichTextBold(f" {teks}")]),
        reply_markup=reply_markup,
    )


async def contact_admins(client, message, topik=None):
    """Dipanggil dari Message (tombol keyboard) ATAU CallbackQuery (tombol inline, mis. Suntik).
    `topik` (opsional): label order yang ikut dikirim ke LOG supaya admin tahu asal pesannya."""
    if client.me.id != bot.id:
        return
    user = message.from_user
    user_id = user.id
    full_name = f"{user.first_name} {user.last_name or ''}".strip()

    if user_id in SUPPORT:
        return await kirim_rich(
            user_id, "info", "Kamu masih dalam sesi kirim pesan, selesaikan dulu."
        )

    SUPPORT.append(user_id)
    try:
        button = ikb(
            [[(" Batalkan", f"batal {user_id}", ButtonStyle.DANGER, "6253758805755038090")]]
        )
        pesan = await bot.ask(
            user_id,
            f"<b>✍️ Tulis pesan anda: {full_name}</b>",
            reply_markup=button,
            timeout=300,
        )
        # sesi sudah dibatalkan lewat tombol Batalkan
        if user_id not in SUPPORT:
            return
        if pesan.text and pesan.text in no_trigger:
            await pesan.delete()
            return await kirim_rich(
                user_id,
                "batal",
                "Proses di batalkan.",
                reply_markup=_menu_awal(user_id),
            )

        buttons = ikb(
            [
                [
                    (" Akun", f"profil {user_id}", ButtonStyle.PRIMARY, "5256143829672672750"),
                ],
                [
                    (" Jawab Pesan", f"jawab_pesan {user_id}", ButtonStyle.SUCCESS, "6046412391887935443"),
                ],
            ]
        )
        if topik:
            await bot.send_message(LOG_SELLER, f"<b>📌 {topik}</b>")
        await pesan.copy(LOG_SELLER, reply_markup=buttons)
        return await kirim_rich(user_id, "sukses", f"Pesan anda terkirim: {full_name}")
    except asyncio.TimeoutError:
        return await kirim_rich(user_id, "info", "Sesi berakhir, silakan coba lagi.")
    except Exception as error:
        if user_id not in SUPPORT:  # dibatalkan user, bukan error
            return
        logger.error(f"Error contact_admins ({user_id}): {traceback.format_exc()}")
        return await kirim_rich(user_id, "gagal", f"ERROR: {error}")
    finally:
        if user_id in SUPPORT:
            SUPPORT.remove(user_id)


async def jawab_pesan(client, callback_query):
    """Tombol 'Jawab Pesan'.
    - Di LOG: hanya admin (SUDO_OWNERS) yang boleh, target = pembeli.
    - Di pesan balasan admin: pembeli boleh, karena target = admin."""
    clicker = callback_query.from_user
    try:
        target_id = int(callback_query.data.split()[1])
    except (IndexError, ValueError):
        return await callback_query.answer("Data tombol tidak valid.", show_alert=True)

    if clicker.id not in SUDO_OWNERS and target_id not in SUDO_OWNERS:
        return await callback_query.answer(
            "Gausah dipencet ya anjing. Lu bukan admin", show_alert=True
        )
    logger.info(f"jawab_pesan: klik oleh {clicker.id}, target {target_id}")

    user_id = clicker.id
    full_name = f"{clicker.first_name} {clicker.last_name or ''}".strip()

    # jawab dulu supaya spinner tombol berhenti sebelum bot.ask menunggu
    try:
        await callback_query.answer()
    except Exception:
        pass

    if user_id in SUPPORT:
        return await kirim_rich(
            user_id, "info", "Kamu masih dalam sesi membalas pesan, selesaikan dulu."
        )

    SUPPORT.append(user_id)
    try:
        button = ikb(
            [[(" Batalkan", f"batal {user_id}", ButtonStyle.DANGER, "6253758805755038090")]]
        )
        pesan = await bot.ask(
            LOG_SELLER,
            user_id,
            f"<b>✉️ Silakan tulis pesan anda: {full_name}</b>",
            reply_markup=button,
            timeout=300,
        )
        if user_id not in SUPPORT:
            return
        if pesan.text and pesan.text in no_trigger:
            await pesan.delete()
            return await kirim_rich(
                user_id,
                "batal",
                "Proses di batalkan.",
                reply_markup=_menu_awal(user_id),
            )

        if target_id != OWNER_ID:
            buttons = ikb(
                [[(" Jawab Pesan", f"jawab_pesan {user_id}", ButtonStyle.SUCCESS, "6046412391887935443")]]
            )
        else:
            buttons = ikb(
                [
                    [
                        (" Akun", f"profil {user_id}", ButtonStyle.PRIMARY, "5256143829672672750"),
                    ],
                    [
                        (" Jawab Pesan", f"jawab_pesan {user_id}", ButtonStyle.SUCCESS, "6046412391887935443"),
                    ],
                ]
            )
        await pesan.copy(target_id, reply_markup=buttons)
        return await kirim_rich(user_id, LOG_SELLER, "sukses", f"Pesan Balasan Terkirim : {full_name}")
    except asyncio.TimeoutError:
        return await kirim_rich(user_id, LOG_SELLER, "info", "Sesi berakhir, silakan coba lagi.")
    except Exception as error:
        if user_id not in SUPPORT:
            return
        logger.error(f"Error jawab_pesan ({user_id}): {traceback.format_exc()}")
        return await kirim_rich(user_id, "gagal", f"ERROR: {error}")
    finally:
        if user_id in SUPPORT:
            SUPPORT.remove(user_id)
          
async def batal_pesan(client, callback_query):
    user_id = callback_query.from_user.id
    try:
        await callback_query.answer()
    except Exception:
        pass
    # hapus dari SUPPORT dulu, supaya contact_admins/jawab_pesan tahu ini dibatalkan
    if user_id in SUPPORT:
        SUPPORT.remove(user_id)
    _batalkan_ask(user_id)
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    return await kirim_rich(
        user_id,
        "batal",
        "Proses di batalkan.",
        reply_markup=_menu_awal(user_id),
    )

async def profil_user(client, callback_query):
    try:
        target_id = int(callback_query.data.split()[1])
        user = await bot.get_users(target_id)
    except Exception as error:
        return await callback_query.answer(f"Gagal: {error}", show_alert=True)
    nama = f"{user.first_name} {user.last_name or ''}".strip()
    username = f"@{user.username}" if user.username else "-"
    return await callback_query.answer(
        f"Nama: {nama}\nID: {user.id}\nUsername: {username}", show_alert=True
    )


async def callback_alert(client, callback_query):
    uniq = callback_query.data.split("_")[1]
    alert_text = await dB.get_var(uniq, f"{uniq}")
    if len(alert_text) > 200:
        return await callback_query.answer(
            "Alert text is too long, please keep it under 200 characters.",
            show_alert=True,
        )
    if r"\n" in alert_text:
        alert_text = alert_text.replace(r"\n", "\n")
    return await callback_query.answer(text=alert_text, show_alert=True)


async def cb_markdown(client, callback_query):
    await callback_query.answer()
    data = callback_query.data.split("_")[1]
    user_id = callback_query.from_user.id
    cekpic = await dB.get_var(user_id, "HELP_LOGO")
    costum_cq = (
        callback_query.edit_message_caption
        if cekpic
        else callback_query.edit_message_text
    )
    full = f"<a href=tg://user?id={callback_query.from_user.id}>{callback_query.from_user.first_name} {callback_query.from_user.last_name or ''}</a>"
    costum_text = "caption" if cekpic else "text"
    prev_page_num = state.get(user_id, "prev_page_num")
    if data == "format":
        try:
            button = ikb(
                [
                    [
                        ("Formatting", "markdown_format", "callback_data"),
                        ("Fillings", "markdown_fillings", "callback_data"),
                    ],
                    [
                        ("🔙 Back", f"help_back({prev_page_num})"),
                    ],
                ]
            )
            return await costum_cq(
                **{costum_text: text_formatting},
                reply_markup=button,
                parse_mode=enums.ParseMode.MARKDOWN,
            )

        except FloodWait as e:
            return await callback_query.answer(f"FloodWait {e}, Please Waiting!!", True)

        except MessageNotModified:
            return
    elif data == "fillings":
        try:
            button = ikb(
                [
                    [
                        ("Formatting", "markdown_format", "callback_data"),
                        ("Fillings", "markdown_fillings", "callback_data"),
                    ],
                    [
                        ("🔙 Back", f"help_back({prev_page_num})"),
                    ],
                ]
            )
            return await costum_cq(
                **{costum_text: text_fillings},
                reply_markup=button,
                parse_mode=enums.ParseMode.MARKDOWN,
            )
        except FloodWait as e:
            return await callback_query.answer(f"FloodWait {e}, Please Waiting!!", True)

        except MessageNotModified:
            return


async def cb_help(client, callback_query):
    await callback_query.answer()
    mod_match = re.match(r"help_module\((.+?),(.+?)\)", callback_query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", callback_query.data)
    next_match = re.match(r"help_next\((.+?)\)", callback_query.data)
    back_match = re.match(r"help_back\((\d+)\)", callback_query.data)
    create_match = re.match(r"help_create", callback_query.data)
    user_id = callback_query.from_user.id
    is_bot = await dB.get_var(user_id, "is_bot")
    is_bot_pro = await dB.get_var(user_id, "is_bot_pro")
    if is_bot:
        is_pro = True if is_bot_pro else False
    else:
        plan = await dB.get_var(user_id, "plan")
        is_pro = True if plan == "is_pro" else False
    visible_helpable = {
        name: data for name, data in HELPABLE.items() if is_pro or not data["is_pro"]
    }
    prefix = navy.get_prefix(user_id)
    x_ = next(iter(prefix))
    full = f"<a href=tg://user?id={callback_query.from_user.id}>{callback_query.from_user.first_name} {callback_query.from_user.last_name or ''}</a>"
    cekpic = await dB.get_var(user_id, "HELP_LOGO")
    text_help = (
        await dB.get_var(user_id, "text_help")
        or f"**🤖 {BOT_NAME} by {USENAME_OWNER}**"
    )
    text_help2 = f"<blockquote>**🤖 {BOT_NAME} by {USENAME_OWNER}**</blockquote>"
    costum_cq = (
        callback_query.edit_message_caption
        if cekpic
        else callback_query.edit_message_text
    )
    costum_text = "caption" if cekpic else "text"
    if mod_match:
        module = mod_match.group(1)
        logger.info(f"line 48: {module}")
        prev_page_num = int(mod_match.group(2))
        state.set(user_id, "prev_page_num", prev_page_num)
        bot_text = f"{visible_helpable[module]['module'].__HELP__}".format(
            x_, text_help2
        )
        if "markdown" in bot_text:
            try:
                button_ = ikb(
                    [
                        [
                            ("Formatting", "markdown_format", "callback_data"),
                            ("Fillings", "markdown_fillings", "callback_data"),
                        ],
                        [
                            ("🔙 Back", f"help_back({prev_page_num})"),
                        ],
                    ]
                )
                return await costum_cq(
                    **{costum_text: text_markdown},
                    reply_markup=button_,
                )
            except FloodWait as e:
                return await callback_query.answer(
                    f"FloodWait {e}, Please Waiting!!", True
                )

            except MessageNotModified:
                return
        else:
            try:
                button = ikb(
                    [
                        [
                            ("🔙 Back", f"help_back({prev_page_num})", "callback_data"),
                        ]
                    ]
                )
                return await costum_cq(
                    **{costum_text: bot_text},
                    reply_markup=button,
                )
            except FloodWait as e:
                return await callback_query.answer(
                    f"FloodWait {e}, Please Waiting!!", True
                )

            except MessageNotModified:
                return

    elif prev_match:
        curr_page = int(prev_match.group(1))
        try:
            return await costum_cq(
                **{
                    costum_text: top_text.format(
                        " ".join(prefix), len(visible_helpable), full, text_help
                    )
                },
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(curr_page, visible_helpable, "help", is_bot=is_bot)
                ),
            )
        except FloodWait as e:
            return await callback_query.answer(f"FloodWait {e}, Please Waiting!!", True)

        except MessageNotModified:
            return
    elif next_match:
        next_page = int(next_match.group(1))
        try:
            return await costum_cq(
                **{
                    costum_text: top_text.format(
                        " ".join(prefix), len(visible_helpable), full, text_help
                    )
                },
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(next_page, visible_helpable, "help", is_bot=is_bot)
                ),
            )
        except FloodWait as e:
            return await callback_query.answer(f"FloodWait {e}, Please Waiting!!", True)

        except MessageNotModified:
            return
    elif back_match:
        prev_page_num = int(back_match.group(1))
        try:
            return await costum_cq(
                **{
                    costum_text: top_text.format(
                        " ".join(prefix), len(visible_helpable), full, text_help
                    )
                },
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(
                        prev_page_num, visible_helpable, "help", is_bot=is_bot
                    )
                ),
            )
        except FloodWait as e:
            return await callback_query.answer(f"FloodWait {e}, Please Waiting!!", True)

        except MessageNotModified:
            return
    elif create_match:
        try:
            return await costum_cq(
                **{
                    costum_text: top_text.format(
                        " ".join(prefix), len(visible_helpable), full, text_help
                    )
                },
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(0, visible_helpable, "help", is_bot=is_bot)
                ),
            )
        except FloodWait as e:
            return await callback_query.answer(f"FloodWait {e}, Please Waiting!!", True)

        except MessageNotModified:
            return


async def del_userbot(client, callback_query):
    tokenref = await TokenReferal.create()
    user_id = callback_query.from_user.id
    if user_id not in SUDO_OWNERS:
        return await callback_query.answer(
            f"<b>GAUSAH DIPENCET YA ANJING! {callback_query.from_user.first_name} {callback_query.from_user.last_name or ''}",
            True,
        )
    await callback_query.answer()
    try:
        show = await bot.get_users(callback_query.data.split()[1])
        get_id = show.id
        get_mention = f"<a href=tg://user?id={get_id}>{show.first_name} {show.last_name or ''}</a>"
    except Exception:
        get_id = int(callback_query.data.split()[1])
        get_mention = f"<a href=tg://user?id={get_id}>Userbot</a>"
    for X in navy._ubot:
        if get_id == X.me.id:
            await X.unblock_user(bot.me.username)
            await dB.remove_ubot(X.me.id)
            await dB.rem_expired_date(X.me.id)
            await tokenref.delete_user_data(str(X.me.id))
            navy._get_my_id.remove(X.me.id)
            navy._ubot.remove(X)
            await X.log_out()
            await bot.send_message(
                LOG_SELLER,
                f"<b> ✅ {get_mention} Deleted on database</b>",
            )
            return await bot.send_message(
                X.me.id,
                f"<b>💬 Masa Aktif Anda Telah Habis</b>\n<b>Ads: {await Message._ads()}</b>",
            )


async def prevnext_userbot(client, callback_query):
    await callback_query.answer()
    query = callback_query.data.split()
    count = int(query[1])
    if query[0] == "next_ub":
        if count == len(navy._ubot) - 1:
            count = 0
        else:
            count += 1
    elif query[0] == "prev_ub":
        if count == 0:
            count = len(navy._ubot) - 1
        else:
            count -= 1
    try:
        return await callback_query.edit_message_text(
            await Message.userbot(count),
            reply_markup=(ButtonUtils.userbot(navy._ubot[count].me.id, count)),
        )
    except Exception as e:
        return f"Error: {e}"


async def prevnext_userbot2(client, callback_query):
    await callback_query.answer()
    query = callback_query.data.split()
    count = int(query[1])
    if query[0] == "fakenext_ub":
        if count == len(navy._ubot) - 1:
            count = 0
        else:
            count += 1
    elif query[0] == "fakeprev_ub":
        if count == 0:
            count = len(navy._ubot) - 1
        else:
            count -= 1
    try:
        return await callback_query.edit_message_text(
            await Message.userbot(count),
            reply_markup=(ButtonUtils.fake_userbot(navy._ubot[count].me.id, count)),
        )
    except Exception as e:
        return f"Error: {e}"


async def tools_userbot(client, callback_query):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    query = callback_query.data.split()
    if user_id not in SUDO_OWNERS:
        return await callback_query.answer(
            f"<b>GAUSAH REWEL YA ANJING! {callback_query.from_user.first_name} {callback_query.from_user.last_name or ''}",
            True,
        )
    X = navy._ubot[int(query[1])]
    if query[0] == "get_otp":
        async for otp in X.search_messages(777000, limit=1):
            try:
                if not otp.text:
                    await callback_query.answer("❌ Kode tidak ditemukan", True)
                else:
                    await callback_query.edit_message_text(
                        otp.text,
                        reply_markup=(ButtonUtils.userbot(X.me.id, int(query[1]))),
                    )
                    return await X.delete_messages(X.me.id, otp.id)
            except Exception as error:
                return await callback_query.answer(error, True)
    elif query[0] == "get_phone":
        try:
            return await callback_query.edit_message_text(
                f"<b>📲 Nomer telepon <code>{X.me.id}</code> adalah <code>{X.me.phone_number}</code></b>",
                reply_markup=(ButtonUtils.userbot(X.me.id, int(query[1]))),
            )
        except Exception as error:
            return await callback_query.answer(error, True)
    elif query[0] == "get_faktor":
        code = await dB.get_var(X.me.id, "PASSWORD")
        if code == None:
            return await callback_query.answer(
                "🔐 Kode verifikasi 2 langkah tidak ditemukan", True
            )
        else:
            return await callback_query.edit_message_text(
                f"<b>🔐 Kode verifikasi 2 langkah pengguna <code>{X.me.id}</code> adalah : <code>{code}</code></b>",
                reply_markup=(ButtonUtils.userbot(X.me.id, int(query[1]))),
            )
    elif query[0] == "ub_deak":
        return await callback_query.edit_message_reply_markup(
            reply_markup=(ButtonUtils.deak(X.me.id, int(query[1])))
        )
    elif query[0] == "deak_akun":
        navy._ubot.remove(X)
        await X.invoke(raw.functions.account.DeleteAccount(reason="madarchod hu me"))
        return await callback_query.edit_message_text(
            Message.deak(X),
            reply_markup=(ButtonUtils.userbot(X.me.id, int(query[1]))),
        )



async def closed_user(client, callback_query):

    try:
        callback_query.from_user
        split = callback_query.data.split(maxsplit=1)[1]
        logger.info(f"ini split {split}")
        data = state.get(split, split)
        logger.info(f"ini data {data}")
        if not data:
            return await callback_query.answer("This button not for you fvck!!", True)
        message = next(
            (obj for obj in get_objects() if id(obj) == int(data["idm"])), None
        )
        c = message._client
        return await c.delete_messages(int(data["chat"]), int(data["_id"]))
    except Exception as er:
        logger.error(f"{str(er)}")


async def pm_warn(app, callback_query):
    try:
        data = callback_query.data.split()
        client = int(data[1])
        target = int(data[2])
        Flood = state.get(client, target)
        pm_warns = await dB.get_var(client, "PMLIMIT") or LIMIT
        return await callback_query.answer(
            f"⚠️ You have a chance {Flood}/{pm_warns} ❗\n\nIf you insist on sending messages continuously then you will be ⛔ blocked automatically and we will 📢 report your account as spam",
            True,
        )
    except Exception:
        logger.error(f"ERROR: {traceback.format_exc()}")


async def get_bio(client, callback_query):
    getid = int(callback_query.data.split("_")[1])
    data = state.get(getid, "bio")
    if not data:
        return await callback_query.answer("Bio not found", True)
    return await callback_query.answer(data, True)


async def copy_msg(client, callback_query):

    try:
        get_id = int(callback_query.data.split("_", 1)[1])
        message = [obj for obj in get_objects() if id(obj) == get_id][0]
        await message._client.unblock_user(bot.me.username)
        await callback_query.edit_message_text("<b>Proses Upload...</b>")
        copy = await message._client.send_message(
            bot.me.username, f"/kontol {message.text.split()[1]}"
        )
        msg = message.reply_to_message or message
        await asyncio.sleep(1.5)
        await copy.delete()
        async for get in message._client.search_messages(bot.me.username, limit=1):
            await message._client.copy_message(
                message.chat.id, bot.me.username, get.id, reply_to_message_id=msg.id
            )
            await message._client.delete_messages(
                message.chat.id, COPY_ID[message._client.me.id]
            )
            await get.delete()
    except Exception as error:
        await callback_query.edit_message_text(f"**ERROR:** <code>{error}</code>")


async def cb_notes(client, callback_query):

    data = callback_query.data.split("_")
    btn_close = state.get("close_notes", "get_note")
    dia = callback_query.from_user
    type_mapping = {
        "photo": InputMediaPhoto,
        "video": InputMediaVideo,
        "animation": InputMediaAnimation,
        "audio": InputMediaAudio,
        "document": InputMediaDocument,
    }
    try:
        notetag = data[-2].replace("cb_", "")
        gw = data[-1]
        item = [x for x in navy._ubot if int(gw) == x.me.id]
        noteval = await dB.get_var(int(gw), notetag, "notes")

        if not noteval:
            await callback_query.answer("Catatan tidak ditemukan.", True)
            return

        full = (
            f"<a href=tg://user?id={dia.id}>{dia.first_name} {dia.last_name or ''}</a>"
        )
        await dB.add_userdata(
            dia.id,
            dia.first_name,
            dia.last_name,
            dia.username,
            dia.mention,
            full,
            dia.id,
        )

        for me in item:
            tks = noteval["result"].get("text")
            note_type = noteval["type"]
            file_id = noteval.get("file_id")
            note, button = ButtonUtils.parse_msg_buttons(tks)
            teks = await Tools.escape_tag(bot, dia.id, note, Tools.parse_words)
            button = await ButtonUtils.create_inline_keyboard(button, int(gw))
            for row in btn_close.inline_keyboard:
                button.inline_keyboard.append(row)
            try:
                if note_type == "text":
                    await callback_query.edit_message_text(
                        text=teks, reply_markup=button
                    )

                elif note_type in type_mapping and file_id:
                    InputMediaType = type_mapping[note_type]
                    media = InputMediaType(media=file_id, caption=teks)
                    await callback_query.edit_message_media(
                        media=media, reply_markup=button
                    )

                else:
                    await callback_query.edit_message_caption(
                        caption=teks, reply_markup=button
                    )

            except FloodWait as e:
                return await callback_query.answer(
                    f"FloodWait {e}, Please Waiting!!", True
                )
            except MessageNotModified:
                pass

    except Exception as e:
        print(f"Error in notes callback: {str(e)}")
        return await callback_query.answer(
            "Terjadi kesalahan saat memproses catatan.", True
        )


async def get_font(_, callback_query):
    try:
        data = str(callback_query.data.split()[1])
        new = str(callback_query.data.split()[2])
        text = state.get(data, "FONT")
        get_new_font = gens_font(new, text)
        await callback_query.answer("Wait a minute!!", True)
        return await callback_query.edit_message_text(
            f"<b>Result:\n<code>{get_new_font}</code></b>"
        )
    except Exception as error:
        return await callback_query.answer(f"❌ Error: {error}", True)


async def prev_font(client, callback_query):

    try:
        get_id = str(callback_query.data.split()[1])
        current_batch = int(callback_query.data.split()[2])
        prev_batch = current_batch - 1

        if prev_batch < 0:
            prev_batch = len(query_fonts) - 1

        keyboard = ButtonUtils.create_font_keyboard(
            query_fonts[prev_batch], get_id, prev_batch
        )

        buttons = InlineKeyboardMarkup(keyboard)
        return await callback_query.edit_message_reply_markup(reply_markup=buttons)
    except Exception as error:
        return await callback_query.answer(f"❌ Error: {error}", True)


async def next_font(client, callback_query):
    try:
        get_id = str(callback_query.data.split()[1])
        current_batch = int(callback_query.data.split()[2])
        next_batch = current_batch + 1

        if next_batch >= len(query_fonts):
            next_batch = 0

        keyboard = ButtonUtils.create_font_keyboard(
            query_fonts[next_batch], get_id, next_batch
        )

        buttons = InlineKeyboardMarkup(keyboard)
        return await callback_query.edit_message_reply_markup(reply_markup=buttons)
    except Exception as error:
        return await callback_query.answer(f"❌ Error: {error}", True)


async def refresh_cat(client, callback_query):
    uniq = str(callback_query.data.split("_")[2])
    await callback_query.answer("Please wait a minute", True)
    buttons = ikb(
        [
            [("Refresh cat", f"refresh_cat_{uniq}")],
            [("Close", f"close inline_cat {uniq}")],
        ]
    )
    r = requests.get("https://api.thecatapi.com/v1/images/search")
    if r.status_code == 200:
        data = r.json()
        cat_url = data[0]["url"]
        if cat_url.endswith(".gif"):
            await callback_query.edit_message_animation(
                cat_url,
                caption="<blockquote><b>Meow 😽</b></blockquote>",
                reply_markup=buttons,
            )
        else:
            await callback_query.edit_message_media(
                InputMediaPhoto(
                    media=cat_url, caption="<blockquote><b>Meow 😽</b></blockquote>"
                ),
                reply_markup=buttons,
            )
    else:
        await callback_query.edit_message_text("Failed to refresh cat picture 🙀")


async def prev_textpro(client, callback_query):
    try:
        get_id = str(callback_query.data.split()[1])
        current_batch = int(callback_query.data.split()[2])
        prev_batch = current_batch - 1

        if prev_batch < 0:
            prev_batch = len(Tools.query_textpro) - 1

        keyboard = ButtonUtils.create_buttons_textpro(
            Tools.query_textpro[prev_batch], get_id, prev_batch
        )

        buttons = InlineKeyboardMarkup(keyboard)
        state.set(get_id, "page_textpro", prev_batch)
        return await callback_query.edit_message_reply_markup(reply_markup=buttons)
    except Exception as error:
        return await callback_query.answer(f"❌ Error: {error}", True)


async def next_textpro(client, callback_query):
    try:
        get_id = str(callback_query.data.split()[1])
        current_batch = int(callback_query.data.split()[2])
        next_batch = current_batch + 1

        if next_batch >= len(Tools.query_textpro):
            next_batch = 0

        keyboard = ButtonUtils.create_buttons_textpro(
            Tools.query_textpro[next_batch], get_id, next_batch
        )

        buttons = InlineKeyboardMarkup(keyboard)
        state.set(get_id, "page_textpro", next_batch)
        return await callback_query.edit_message_reply_markup(reply_markup=buttons)
    except Exception as error:
        return await callback_query.answer(f"❌ Error: {error}", True)


async def gen_pro(client, callback_query):
    await callback_query.answer("Wait a minute!!", True)
    query = callback_query.data.split()
    uniq = str(query[1])
    command = str(query[2])
    text = state.get(uniq, "TEXT_PRO")
    result_image = await Tools.gen_text_pro(text, command)
    page = state.get(uniq, "page_textpro")
    keyboard = ButtonUtils.create_buttons_textpro(
        Tools.query_textpro[0], uniq, current_batch=int(page)
    )
    buttons = InlineKeyboardMarkup(keyboard)
    if not result_image.startswith("ERROR"):
        logger.info(f"Result TextPro: {result_image}")
        try:
            image = InputMediaPhoto(
                media=result_image,
                caption=f"<blockquote>**Costum text:**\n\n{text}</blockquote>",
            )
            await callback_query.edit_message_media(media=image, reply_markup=buttons)
        except Exception as e:

            logger.error(f"Line 656: {traceback.format_exc()}")
            await callback_query.edit_message_text(f"Failed to send image: {str(e)}")
    else:
        logger.error(f"Line 659: {traceback.format_exc()}")
        await callback_query.edit_message_text(
            f"Failed to generate text pro:\n{result_image}"
        )


async def bola_date(client, callback_query):

    split = callback_query.data.split()
    if len(split) > 1:
        state_key = split[1]
        stored_data = state.get(state_key, state_key)

        buttons = []
        temp_row = []
        for liga_date in stored_data:
            button = Ikb(
                text=liga_date["LigaDate"],
                callback_data=f"bola_matches {state_key} {liga_date['LigaDate']}",
            )
            temp_row.append(button)

            if len(temp_row) == 3:
                buttons.append(temp_row)
                temp_row = []

        if temp_row:
            buttons.append(temp_row)

        buttons.append(
            [Ikb(text="Close", callback_data=f"close inline_bola {state_key}")]
        )
        keyboard = InlineKeyboardMarkup(buttons)

        return await callback_query.edit_message_text(
            text="<b>Select a date to view football matches:</b>",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    else:
        return await callback_query.edit_message_text("No data found.")


async def bola_matches(client, callback_query):
    split = callback_query.data.split()
    if len(split) > 2:
        state_key = split[1]
        selected_date = split[2]
        stored_data = state.get(state_key, "jadwal_bola")

        date_matches = next(
            (
                date
                for date in stored_data
                if date["LigaDate"].split()[0] == selected_date.split()[0]
            ),
            None,
        )

        if date_matches:
            text = f"Football Matches on {selected_date}\n\n"
            for league in date_matches["LigaItem"]:
                text += f"🏆 {league['NameLiga']}\n"
                for match in league["Match"]:
                    text += f"⚽ {match['team']} at {match['time']}\n"

            buttons = [
                [Ikb(text="« Back", callback_data=f"bola_date {state_key}")],
                [Ikb(text="Close", callback_data=f"close inline_bola {state_key}")],
            ]
            keyboard = InlineKeyboardMarkup(buttons)

            return await callback_query.edit_message_text(
                text=f"<blockquote><b>{text}</b></blockquote>",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        else:
            return await callback_query.answer("Silahkan ulangi fitur bola!!", True)


async def rest_anime(client, callback_query):
    data = callback_query.data.split("_")
    page = int(data[1])
    uniq = str(data[2])
    berita = state.get(uniq, "anime")
    if not berita:
        await callback_query.answer("Halaman tidak ditemukan.", show_alert=True)
        return
    total_photos = len(berita)
    if page < 0 or page >= total_photos:
        await callback_query.answer("Halaman tidak ditemukan.", show_alert=True)
        return
    buttons = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(Ikb("⬅️ Prev", callback_data=f"restanime_{page - 1}_{uniq}"))
    if page < total_photos - 1:
        nav_buttons.append(Ikb("➡️ Next", callback_data=f"restanime_{page + 1}_{uniq}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([Ikb("❌ Close", callback_data=f"close inline_anime {uniq}")])
    title = berita[page].get("title", "-")
    jap_title = berita[page].get("title", "-")
    desc = berita[page].get("description", "-")
    desc = (desc[:400] + "...") if len(desc) > 400 else desc
    adult = berita[page].get("adultContent", "-")
    thumb = berita[page].get("poster")
    showin = berita[page]["tvInfo"]
    showType = showin.get("showType", "-")
    duration = showin.get("duration", "-")
    caption = f"""
📺 **Title:** `{title}`
🇯🇵 **Japanese Title:** `{jap_title}`
📝 **Description:** `{desc}`
🔞 **Adult Content:** `{adult}`
🎬 **Event Type:** `{showType}`
⏱️ **Duration:** `{duration}`
"""
    reply_markup = InlineKeyboardMarkup(buttons)
    return await callback_query.edit_message_media(
        media=InputMediaPhoto(media=thumb, caption=caption),
        reply_markup=reply_markup,
    )


async def rest_donghua(client, callback_query):
    data = callback_query.data.split("_")
    page = int(data[1])
    uniq = str(data[2])
    berita = state.get(uniq, "donghua")
    if not berita:
        await callback_query.answer("Halaman tidak ditemukan.", show_alert=True)
        return
    total_photos = len(berita)
    if page < 0 or page >= total_photos:
        await callback_query.answer("Halaman tidak ditemukan.", show_alert=True)
        return
    buttons = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            Ikb("⬅️ Prev", callback_data=f"restdonghua_{page - 1}_{uniq}")
        )
    if page < total_photos - 1:
        nav_buttons.append(
            Ikb("➡️ Next", callback_data=f"restdonghua_{page + 1}_{uniq}")
        )
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([Ikb("❌ Close", callback_data=f"close inline_donghua {uniq}")])
    title = berita[page].get("title")
    episode = berita[page].get("episode")
    date = Tools.jakartaTime(berita[page].get("updatedAt", "-"))
    url = berita[page].get("url")
    judul = f"**Title:** {title}\n**Episode:** {episode}\n**Link:** {url}\n**Uploaded:** {date}"
    thumb = berita[page].get("thumbnail")
    reply_markup = InlineKeyboardMarkup(buttons)
    return await callback_query.edit_message_media(
        media=InputMediaPhoto(media=thumb, caption=judul),
        reply_markup=reply_markup,
    )


async def rest_comic(client, callback_query):
    data = callback_query.data.split("_")
    page = int(data[1])
    uniq = str(data[2])
    berita = state.get(uniq, "comic")
    if not berita:
        await callback_query.answer("Halaman tidak ditemukan.", show_alert=True)
        return
    total_photos = len(berita)
    if page < 0 or page >= total_photos:
        await callback_query.answer("Halaman tidak ditemukan.", show_alert=True)
        return
    buttons = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(Ikb("⬅️ Prev", callback_data=f"restcomic_{page - 1}_{uniq}"))
    if page < total_photos - 1:
        nav_buttons.append(Ikb("➡️ Next", callback_data=f"restcomic_{page + 1}_{uniq}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([Ikb("❌ Close", callback_data=f"close inline_comic {uniq}")])
    title = berita[page].get("title")
    chapter = berita[page].get("chapters", [{}])[0]
    episode = chapter.get("title", "-")
    date = chapter.get("date", "-")
    chapter_url = chapter.get("url", "")
    if "https://komiku.id" in chapter_url and not chapter_url.startswith(
        "https://komiku.id/"
    ):
        chapter_url = chapter_url.replace("https://komiku.id", "https://komiku.id/")
    judul = f"**Title:** {title}\n**Chapters:** {episode}\n**Link:** {chapter_url}\n**Uploaded:** {date}"
    reply_markup = InlineKeyboardMarkup(buttons)
    await callback_query.edit_message_text(judul, reply_markup=reply_markup)


async def news_(client, callback_query):
    data = callback_query.data.split("_")
    page = int(data[1])
    uniq = str(data[2])
    berita = state.get(uniq, "news")
    if not berita:
        await callback_query.answer(
            "Tidak ada berita untuk ditampilkan.", show_alert=True
        )
        return
    total_photos = len(berita)
    if page < 0 or page >= total_photos:
        await callback_query.answer("Halaman tidak ditemukan.", show_alert=True)
        return
    buttons = []
    nav_buttons = []
    buttons.append([Ikb("📮 Link", url=f"{berita[page]['url']}")])
    if page > 0:
        nav_buttons.append(Ikb("⬅️ Prev", callback_data=f"news_{page - 1}_{uniq}"))
    if page < total_photos - 1:
        nav_buttons.append(Ikb("➡️ Next", callback_data=f"news_{page + 1}_{uniq}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([Ikb("❌ Close", callback_data=f"close inline_news {uniq}")])
    title = berita[page]["title"]
    date = berita[page].get("berita_diupload", "-")
    thumb = berita[page]["thumbnail"]
    judul = f"""
**Title:** {title}
**Uploaded:** {date}"""
    reply_markup = InlineKeyboardMarkup(buttons)
    return await callback_query.edit_message_media(
        media=InputMediaPhoto(media=thumb, caption=judul),
        reply_markup=reply_markup,
    )


async def select_model(client, query):
    uniq = str(query.data.split("_")[1])
    msg = "**Please choose model for AI:**"
    buttons = ikb(
        [
            [
                ("ChatGpt", f"chatai_chatgpt_{uniq}"),
                ("DeepSeek", f"chatai_deepseek_{uniq}"),
            ],
            [
                ("Gemini", f"chatai_gemini_{uniq}"),
                ("BlackBox", f"chatai_blackbox_{uniq}"),
            ],
        ]
    )
    return await query.edit_message_text(msg, reply_markup=buttons)


async def chatai_with_chatgpt_normal(client, query, uniq):
    data = state.get(uniq, "chatai")
    prompt = data["prompt"]
    get_id = data["idm"]
    message = [obj for obj in get_objects() if id(obj) == get_id][0]
    user_id = message.from_user.id
    chat_id = message.chat.id
    ids = (unpack_inline_message_id(query.inline_message_id)).id
    try:
        await message._client.delete_messages(
            message.chat.id,
            ids,
        )
    except Exception:
        pass
    if user_id not in CONVERSATIONS:
        CONVERSATIONS[user_id] = [
            {
                "role": "system",
                "content": "Kamu adalah asisten paling canggih yang berbahasa Indonesia gaul, dan jangan gunakan bahasa inggris sebelum saya memulai duluan.",
            },
            {
                "role": "assistant",
                "content": "Kamu adalah asisten paling canggih yang berbahasa Indonesia gaul",
            },
        ]
    while True:
        try:
            url = "https://api.botcahx.eu.org/api/search/openai-custom"
            CONVERSATIONS[user_id].append({"role": "user", "content": prompt})
            payload = {"message": CONVERSATIONS[user_id], "apikey": API_BOTCHAX}
            r = await Tools.fetch.post(url, json=payload)
            if r.status_code == 200:
                result = r.json().get("result")
                CONVERSATIONS[user_id].append({"role": "assistant", "content": prompt})
                if len(CONVERSATIONS[user_id]) > 20:
                    CONVERSATIONS[user_id] = (
                        CONVERSATIONS[user_id][:2] + CONVERSATIONS[user_id][-18:]
                    )
                if len(result) > 4096:
                    with open(f"{prompt.split()[1]}.txt", "wb") as file:
                        file.write(result.encode("utf-8"))
                    reply = await message._client.send_document(
                        chat_id, f"{prompt.split()[1]}.txt"
                    )
                    next_message = await message._client.ask(
                        chat_id,
                        f"<b><u>Chat with ChatGpt</u></b>\nQuestion:</b>\n<blockquote>{prompt}</blockquote>\n\n**Type `stopped ask` to end the conversation.**",
                        reply_to_message_id=reply.id,
                        timeout=300,
                    )
                else:
                    next_message = await message._client.ask(
                        chat_id,
                        f"<b><u>Chat with ChatGpt</u></b>\n<b>Question:\n<blockquote>{prompt}</blockquote>\n\nAnswer:\n</b><blockquote>{result}</blockquote>\n\n**Type `stopped ask` to end the conversation.**",
                    )
                    if next_message.text.lower() == "stopped ask":
                        del CONVERSATIONS[user_id]
                        await next_message.reply(f"**Conversation ended.**")
                        break
                    prompt = next_message.text
            else:
                return await message.reply("<b>Please try again later..</b>")
        except Exception:
            logger.error(traceback.format_exc())
            return await message.reply("<b>Please try again later..</b>")


async def chat_gpt(client, query):
    mode = str(query.data.split("_")[1])
    uniq = str(query.data.split("_")[2])
    data = state.get(uniq, "chatai")
    if not data:
        return await query.answer(
            "Data not found, please create new conversation.", True
        )
    if mode == "normal":
        return await chatai_with_chatgpt_normal(client, query, uniq)
    elif mode == "audio":
        msg = "<b>Please select model voice first.</b>"
        models = [
            "alloy",
            "echo",
            "fable",
            "onyx",
            "nova",
            "shimmer",
            "coral",
            "verse",
            "ballad",
            "ash",
            "sage",
            "amuch",
            "dan",
            "elan",
        ]

        buttons = []
        row = []
        for idx, model in enumerate(models, 1):
            row.append(
                Ikb(model.capitalize(), callback_data=f"gptvoice_{model}_{uniq}")
            )
            if idx % 3 == 0:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        reply_markup = InlineKeyboardMarkup(buttons)
        return await query.edit_message_text(msg, reply_markup=reply_markup)


async def gpt_voice(client, callback_query):
    data = callback_query.data.split("_")
    args = str(data[1])
    uniq = str(data[2])
    query = state.get(uniq, "chatai")
    if not query:
        return await callback_query.answer(
            "Data telah usang. Silahkan jalankan ulang fitur nya.", True
        )
    prompt = query["prompt"]
    get_id = query["idm"]
    message = [obj for obj in get_objects() if id(obj) == get_id][0]
    chat_id = message.chat.id
    user_id = message.from_user.id
    ids = (unpack_inline_message_id(callback_query.inline_message_id)).id
    try:
        await message._client.delete_messages(
            message.chat.id,
            ids,
        )
    except Exception:
        pass
    if user_id not in CONVERSATIONS:
        CONVERSATIONS[user_id] = []
    while True:
        try:
            headers = {"mg-apikey": API_MAELYN}
            params = {"q": prompt, "model": args}
            url = "https://api.maelyn.sbs/api/chatgpt/audio"
            response = await Tools.fetch.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()["result"]
                audio = data.get("url")
                CONVERSATIONS[user_id].append(audio)
                reply = await message._client.send_audio(chat_id, audio)
                next_message = await message._client.ask(
                    chat_id,
                    f"**Model: {args}**\n\n<b>Question:\n<blockquote>{prompt}</blockquote>\n\n**Type `stopped ask` to end the conversation.**",
                    reply_to_message_id=reply.id,
                )
                if next_message.text.lower() == "stopped ask":
                    del CONVERSATIONS[user_id]
                    await next_message.reply(f"**Conversation ended.**")
                    break
                prompt = next_message.text
            else:
                return await message.reply("<b>Please try again later..</b>")
        except Exception:
            logger.error(traceback.format_exc())
            return await message.reply("<b>Please try again later..</b>")


async def cine_plax(_, callback_query):
    data = callback_query.data.split("_")
    uniq = str(data[2])
    page = int(data[1])
    type_ = state.get(uniq, "cineplax")
    movies = state.get(uniq, "data_cineplax", [])
    if page * 5 >= len(movies):
        await callback_query.answer("Tidak ada halaman berikutnya.", show_alert=True)
        return

    buttons = []
    for movie in movies[page * 5 : (page + 1) * 5]:
        rating = movie.get("label", "-").split("/")[-1].replace(".png", "")
        if type_ == "soon":
            link = movie["link"].replace("https://21cineplex.com/comingsoon", "", 1)
        else:
            link = movie["link"].replace("https://21cineplex.com/", "", 1)
    if page > 0:
        buttons.append([Ikb("📮 Link", url=link)])
        buttons.append(
            [
                Ikb("⬅️ Prev", callback_data=f"cineplax_{page - 1}_{uniq}"),
                Ikb("➡️ Next", callback_data=f"cineplax_{page + 1}_{uniq}"),
            ]
        )
    buttons.append([Ikb("❌ Close", callback_data=f"close inline_cineplax {uniq}")])
    reply_markup = InlineKeyboardMarkup(buttons)

    caption = f"""
<blockquote>🎬 **Title: {movie['title']}**

**Rating:** {rating}</blockquote>
"""
    await callback_query.edit_message_media(
        media=InputMediaPhoto(
            media=movie["poster"],
            caption=caption,
        ),
        reply_markup=reply_markup,
    )


async def cek_expired_cb(client, cq):
    user_id = int(cq.data.split()[1])
    try:
        expired = await dB.get_expired_date(user_id)
        habis = expired.astimezone(timezone("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M")
        return await cq.answer(f"⏳ Waktu: {habis}", True)
    except Exception:
        return await cq.answer("✅ Sudah tidak aktif", True)


async def closed_bot(client, cq):
    await cq.answer()
    if await dB.get_var(cq.from_user.id, "is_bot"):
        await dB.remove_var(cq.from_user.id, "is_bot")
        await dB.remove_var(cq.from_user.id, "is_bot_pro")
    return await cq.message.delete()


async def callback_cerpen(client, callback):
    await callback.answer("Please wait a minute", True)
    query = callback.data.split("_")
    page = int(query[1])
    uniq = str(query[2])
    cerpen_data = state.get(uniq, uniq)
    if not cerpen_data:
        return await callback.answer(
            "Data telah usang, Silahkan ulangi perintah cerpen"
        )
    total_cerpen = len(cerpen_data)
    if page < 0 or page >= total_cerpen:
        return await callback.answer("Halaman tidak ditemukan.", show_alert=True)
    buttons = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(Ikb("⬅️ Prev", callback_data=f"cerpennext_{page - 1}_{uniq}"))
    if page < total_cerpen - 1:
        nav_buttons.append(Ikb("➡️ Next", callback_data=f"cerpennext_{page + 1}_{uniq}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([Ikb("❌ Close", callback_data=f"close inline_cerpen {uniq}")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await callback.edit_message_text(cerpen_data[page], reply_markup=reply_markup)


async def dln_youtube(app, callback):
    await callback.answer("Please wait a minute", True)
    query = callback.data.split("_")
    target = str(query[1])
    uniq = str(query[2])
    now = time.time()
    as_video = True if target == "video" else False
    query = state.get(uniq, "query")
    if not query:
        return await callback.answer("Data not found, please try again!!", True)
    get_id = state.get(uniq, "idm")
    message = [obj for obj in get_objects() if id(obj) == get_id][0]
    client = message._client
    emo = Emoji(client)
    await emo.get()
    ids = (unpack_inline_message_id(callback.inline_message_id)).id
    try:
        await message._client.delete_messages(message.chat.id, ids)
    except Exception:
        pass
    proses = await animate_proses(message, emo.proses)
    try:
        yt_search = YoutubeSearch(query, max_results=1)
        await yt_search.fetch_results()
        link = yt_search.get_link()
        logger.info(f"Link: {link}")
    except Exception as error:
        return await proses.edit(f"{emo.gagal}<b>ERROR:</b><code>{str(error)}</code>")
    try:
        (
            file_name,
            inpoh,
            title,
            duration,
            views,
            channel,
            url,
            _,
            thumb,
            data_ytp,
        ) = await youtube.download(link, as_video=as_video)

        if isinstance(duration, str):
            duration = duration.replace(".", "")
        duration = int(duration)

    except Exception as error:
        return await proses.edit(f"{emo.gagal}<b>ERROR:</b><code>{str(error)}</code>")

    thumbnail = wget.download(thumb)
    kapten = data_ytp.format(
        inpoh,
        title,
        timedelta(seconds=duration),
        views,
        channel,
        url,
        bot.me.mention,
    )

    if as_video:
        await client.send_video(
            message.chat.id,
            video=file_name,
            thumb=thumbnail,
            file_name=title,
            duration=duration,
            supports_streaming=True,
            caption=f"{kapten}",
            progress=youtube.progress,
            progress_args=(
                proses,
                now,
                f"{emo.proses}<b>Trying to upload...</b>",
                f"{file_name}",
            ),
            reply_to_message_id=message.id,
        )
    else:
        await client.send_audio(
            message.chat.id,
            audio=file_name,
            thumb=thumbnail,
            file_name=title,
            performer=channel,
            duration=duration,
            caption=f"{kapten}",
            progress=youtube.progress,
            progress_args=(
                proses,
                now,
                f"{emo.proses}<b>Trying to upload...</b>",
                f"{file_name}",
            ),
            reply_to_message_id=message.id,
        )
    await proses.delete()
    if os.path.exists(thumbnail):
        os.remove(thumbnail)
    if os.path.exists(file_name):
        os.remove(file_name)


async def generate_data_tiktok(app, callback, uniq):
    await callback.answer("Please wait a minute", True)
    arg = state.get(uniq, "query")
    if not arg:
        return await callback.answer("Data not found, please try again!!", True)
    url = f"https://api.botcahx.eu.org/api/search/tiktoks?query={arg}&apikey={API_BOTCHAX}"
    response = await Tools.fetch.get(url)
    if response.status_code == 200:
        data = response.json()["result"]
        if len(data["data"]) == 0:
            buttons = ikb([[("Close", f"close inline_sosmed {uniq}")]])
            return await callback.edit_message_text(
                f"**Try another word, no videos found `{arg}`**", reply_markup=buttons
            )
        get_id = state.get(uniq, "idm")
        message = [obj for obj in get_objects() if id(obj) == get_id][0]
        client = message._client
        em = Emoji(client)
        await em.get()
        ids = (unpack_inline_message_id(callback.inline_message_id)).id
        try:
            await message._client.delete_messages(message.chat.id, ids)
        except Exception:
            pass
        proses = await animate_proses(message, em.proses)
        state.set(uniq, "tiktoks_search", data["data"])
        inline = await ButtonUtils.send_inline_bot_result(
            message,
            message.chat.id,
            bot.me.username,
            f"inline_ttsearch {uniq}",
        )
        if inline:
            await proses.delete()
        else:
            return await proses.edit(f"{em.gagal}**ERROR Please contact developer.*")
    else:
        return await proses.edit(
            f"{em.gagal}**Please try again {response.status_code}**"
        )


async def generate_data_pinterest(app, callback, uniq):
    await callback.answer("Please wait a minute", True)
    prompt = state.get(uniq, "query")
    if not prompt:
        return await callback.answer("Data not found, please try again!!", True)
    url = f"https://api.botcahx.eu.org/api/search/pinterest?text1={prompt}&apikey={API_BOTCHAX}"
    response = await Tools.fetch.get(url)
    if response.status_code == 200:
        data = response.json()
        if len(data["result"]) == 0:
            buttons = ikb([[("Close", f"close inline_sosmed {uniq}")]])
            return await callback.edit_message_text(
                f"**Try another word, no data found `{prompt}`**", reply_markup=buttons
            )
        get_id = state.get(uniq, "idm")
        message = [obj for obj in get_objects() if id(obj) == get_id][0]
        client = message._client
        em = Emoji(client)
        await em.get()
        ids = (unpack_inline_message_id(callback.inline_message_id)).id
        try:
            await message._client.delete_messages(message.chat.id, ids)
        except Exception:
            pass
        proses = await animate_proses(message, em.proses)
        state.set(uniq, "pinterest", data["result"])
        inline = await ButtonUtils.send_inline_bot_result(
            message,
            message.chat.id,
            bot.me.username,
            f"inline_pinsearch {uniq}",
        )
        if inline:
            return await proses.delete()
        else:
            return await proses.edit(f"{em.gagal}**ERROR Please contact developer.*")
    else:
        return await proses.edit(
            f"{em.gagal}**No images were found for these keywords!**"
        )


async def generate_data_spotify(app, callback, uniq):
    await callback.answer("Please wait a minute", True)
    arg = state.get(uniq, "query")
    if not arg:
        return await callback.answer("Data not found, please try again!!", True)
    url = f"https://api.botcahx.eu.org/api/search/spotify?query={arg}&apikey={API_BOTCHAX}"
    response = await Tools.fetch.get(url)
    if response.status_code == 200:
        data = response.json()["result"]
        if len(data["data"]) == 0:
            buttons = ikb([[("Close", f"close inline_sosmed {uniq}")]])
            return await callback.edit_message_text(
                f"**Try another word, no audio found `{arg}`**", reply_markup=buttons
            )
        get_id = state.get(uniq, "idm")
        message = [obj for obj in get_objects() if id(obj) == get_id][0]
        client = message._client
        em = Emoji(client)
        await em.get()
        ids = (unpack_inline_message_id(callback.inline_message_id)).id
        try:
            await message._client.delete_messages(message.chat.id, ids)
        except Exception:
            pass
        proses = await animate_proses(message, em.proses)
        state.set(uniq, uniq, data["data"])
        state.set(uniq, "idm_spotdl", id(message))
        inline = await ButtonUtils.send_inline_bot_result(
            message,
            message.chat.id,
            bot.me.username,
            f"inline_spotify {uniq}",
        )
        if inline:
            await proses.delete()
        else:
            return await proses.edit(f"{em.gagal}**ERROR Please contact developer.*")
    else:
        return await proses.edit(
            f"{em.gagal}**Please try again {response.status_code}**"
        )


async def nxt_tsearch(_, callback_query):
    data = callback_query.data.split("_")
    await callback_query.answer("Please wait a minute", True)
    page = int(data[1])
    uniq = str(data[2])
    videos = state.get(uniq, "tiktoks_search")
    if videos is None:
        await callback_query.answer("Tidak ada halaman berikutnya.", show_alert=True)
        return
    buttons = []
    video_link = None
    for video in videos[page * 5 : (page + 1) * 5]:
        title = video["title"]
        video_link = video["play"]
        caption = f"<blockquote>{title}</blockquote>"

    if page > 0:
        buttons.append(
            [
                Ikb("Prev video", callback_data=f"nxttsearch_{page - 1}_{uniq}"),
                Ikb("Next video", callback_data=f"nxttsearch_{page + 1}_{uniq}"),
            ]
        )
        buttons.append([Ikb("Close", callback_data=f"close inline_ttsearch {uniq}")])
    else:
        buttons.append(
            [
                Ikb("Next video", callback_data=f"nxttsearch_{page + 1}_{uniq}"),
            ]
        )
        buttons.append([Ikb("Close", callback_data=f"close inline_ttsearch {uniq}")])
    reply_markup = InlineKeyboardMarkup(buttons)
    return await callback_query.edit_message_media(
        media=InputMediaVideo(
            media=video_link,
            caption=caption,
        ),
        reply_markup=reply_markup,
    )


async def cq_tiktok(client, callback_query):

    try:
        data = callback_query.data.split("_")
        uniq = str(data[2])
        query = str(data[1])
        results = state.get(uniq, "result_ttdownload")
        get_id = state.get(uniq, "idm_ttdownload")
        message = [obj for obj in get_objects() if id(obj) == get_id][0]
        if query == "videodl":
            video_link = results["video"][0]
            caption = results["title"]
            logger.info(f"Video tiktok link: {video_link}")
            await callback_query.edit_message_text(
                "**Please wait, trying to send the video...**"
            )
            video = f"downloads/{uniq}.mp4"
            await Tools.bash(f"curl -L {video_link} -o {video}")
            await message.reply_video(video, caption=caption)
            if os.path.exists(video):
                os.remove(video)
            await asyncio.sleep(2)
            ids = (unpack_inline_message_id(callback_query.inline_message_id)).id
            try:
                return await message._client.delete_messages(message.chat.id, ids)
            except Exception:
                pass
        elif query == "audiodl":
            audio_link = results["audio"][0]
            caption = results["title"]
            logger.info(f"Audio tiktok link: {audio_link}")
            await callback_query.edit_message_text(
                "**Please wait, trying to send the audio...**"
            )
            audio = f"downloads/{uniq}.mp3"
            await Tools.bash(f"curl -L {audio_link} -o {audio}")
            await message.reply_audio(audio, caption=caption)
            await asyncio.sleep(2)
            if os.path.exists(audio):
                os.remove(audio)
            ids = (unpack_inline_message_id(callback_query.inline_message_id)).id
            try:
                return await message._client.delete_messages(message.chat.id, ids)
            except Exception:
                pass
    except Exception as er:
        logger.error(f"Cq tiktok dl: {traceback.format_exc()}")
        return await callback_query.edit_message_text(f"**An errror:** {str(er)}")


async def nxt_spotify(_, callback_query):
    data = callback_query.data.split("_")
    await callback_query.answer("Please wait a minute", True)
    page = int(data[1])
    uniq = str(data[2])
    audios = state.get(uniq, uniq)
    if audios is None:
        await callback_query.answer("Tidak ada halaman berikutnya.", show_alert=True)
        return

    buttons = []
    for audio in audios[page * 5 : (page + 1) * 5]:
        caption = f"""<blockquote>
🎶 **Title:** {audio['title']}
👥 **Popularity:** {audio['popularity']}
⏳ **Duration:** {audio['duration']}
🖇️ **Spotify URL:** <a href='{audio['url']}'>here</a></blockquote>"""
        state.set(uniq, "fordlspotify", audio["url"])
        logger.info(f"Url line 796: {audio['url']}")
    buttons.append([Ikb("Download audio", callback_data=f"dlspot_{uniq}")])
    if page > 0:
        buttons.append(
            [
                Ikb("Prev audio", callback_data=f"nxtspotify_{page - 1}_{uniq}"),
                Ikb("Next audio", callback_data=f"nxtspotify_{page + 1}_{uniq}"),
            ]
        )
        buttons.append([Ikb("Close", callback_data=f"close inline_spotify {uniq}")])
    else:
        buttons.append(
            [
                Ikb("Next audio", callback_data=f"nxtspotify_{page + 1}_{uniq}"),
            ]
        )
        buttons.append([Ikb("Close", callback_data=f"close inline_spotify {uniq}")])
    reply_markup = InlineKeyboardMarkup(buttons)
    return await callback_query.edit_message_text(
        caption, reply_markup=reply_markup, disable_web_page_preview=True
    )


async def dl_spot(_, callback_query):
    try:
        data = callback_query.data.split("_")
        await callback_query.answer("Please wait a minute", True)
        uniq = str(data[1])
        data = state.get(uniq, uniq)
        get_id = state.get(uniq, "idm_spotdl")
        message = [obj for obj in get_objects() if id(obj) == get_id][0]
        client = message._client
        em = Emoji(client)
        await em.get()
        now = time.time()
        link = data[0]["url"]
        proses = await message.reply(f"{em.proses}**Get detail information...**")
        url = await Spotify.track(link)
        (
            file_path,
            info,
            title,
            duration,
            views,
            channel,
            url,
            _,
            thumb,
            data_ytp,
        ) = await youtube.download(url.get("file_path"), as_video=False)
        thumbnail = wget.download(thumb)
        caption = data_ytp.format(
            info,
            title,
            timedelta(seconds=duration),
            views,
            channel,
            url,
            client.me.mention,
        )
        ids = (unpack_inline_message_id(callback_query.inline_message_id)).id
        try:
            await client.delete_messages(
                message.chat.id,
                ids,
            )
        except Exception:
            pass
        try:
            await message.reply_audio(
                audio=file_path,
                title=title,
                thumb=thumbnail,
                performer=channel,
                duration=duration,
                caption=caption,
                progress=youtube.progress,
                progress_args=(proses, now, f"<b>Sending request...</b>", f"{title}"),
            )
            return await proses.delete()
        except Exception:
            logger.error(f"Eror download spotify: {traceback.format_exc()}")
            return await proses.edit(f"{em.gagal}**ERROR Please contact developer.*")
    except Exception:
        logger.error(f"Eror download spotify: {traceback.format_exc()}")


async def nxpin_search(_, callback_query):

    data = callback_query.data.split("_")
    page = int(data[1])
    uniq = str(data[2])
    photos = state.get(uniq, "pinterest")

    if not photos:
        await callback_query.answer(
            "Tidak ada foto untuk ditampilkan.", show_alert=True
        )
        return

    total_photos = len(photos)

    if page < 0 or page >= total_photos:
        await callback_query.answer("Halaman tidak ditemukan.", show_alert=True)
        return

    buttons = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            Ikb("⬅️ Prev", callback_data=f"nxpinsearch_{page - 1}_{uniq}")
        )
    if page < total_photos - 1:
        nav_buttons.append(
            Ikb("➡️ Next", callback_data=f"nxpinsearch_{page + 1}_{uniq}")
        )

    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([Ikb("❌ Close", callback_data=f"close inline_pinsearch {uniq}")])

    reply_markup = InlineKeyboardMarkup(buttons)

    await callback_query.edit_message_media(
        media=InputMediaPhoto(media=photos[page]), reply_markup=reply_markup
    )


async def sosmed_callback(client, callback):
    query = callback.data.split("_")
    target = str(query[1])
    uniq = str(query[2])
    if target == "yt":
        buttons = ikb(
            [
                [
                    ("Download Video", f"dlnyt_video_{uniq}"),
                    ("Download Audio", f"dlnyt_audio_{uniq}"),
                ]
            ]
        )
        return await callback.edit_message_text(
            f"**Please select what wanna you download**", reply_markup=buttons
        )
    elif target == "tt":
        return await generate_data_tiktok(client, callback, uniq)
    elif target == "pin":
        return await generate_data_pinterest(client, callback, uniq)
    elif target == "spot":
        return await generate_data_spotify(client, callback, uniq)


async def viewchord(client, callback):
    query = callback.data.split("_")
    index = int(query[1])
    uniq = str(query[2])
    data = state.get(uniq, "chord")
    if index < 0 or index >= len(data):
        return await callback.answer("Data tidak ditemukan!", True)
    await callback.answer("Please wait a moment!!", True)
    song = data[index]
    song_url = song.get("url", "-")
    url = f"https://nolimitdev.cloud/api/search/chord?url={song_url}"
    response = await Tools.fetch.get(url)
    buttons = ikb([[("Close", f"close inline_chord {uniq}")]])
    if response.status_code != 200:
        return await callback.edit_message_text(
            f"**Please try again later!!: {response.status_code}**",
            reply_markup=buttons,
        )
    result = response.json()["result"]
    msg = f"""
**Title: {result.get('title', '-')}**
**Date: {result.get('date', '-')}**
**Author: {result.get('author', '-')}
**Chord:**
{result.get('chord', '-')}
"""
    return await callback.edit_message_text(msg, reply_markup=buttons)


async def viewlyric(client, callback):
    query = callback.data.split("_")
    index = int(query[1])
    uniq = str(query[2])
    data = state.get(uniq, "lyric")
    if index < 0 or index >= len(data):
        return await callback.answer("Data tidak ditemukan!", True)

    await callback.answer("Please wait a moment!!", True)

    lirik = data[index]["result"]
    lirik_url = lirik.get("url", "-")
    url = f"https://nolimitdev.cloud/api/search/lyric?url={lirik_url}"
    response = await Tools.fetch.get(url)

    buttons = ikb([[("Close", f"close inline_lyric {uniq}")]])

    if response.status_code != 200:
        return await callback.edit_message_text(
            f"**Please try again later!!: {response.status_code}**",
            reply_markup=buttons,
        )

    result = response.json()["result"]
    raw_lyrics = result.get("lirik", "")

    match = re.search(r"(\[Intro\]|\[Verse.*?\]|\[Chorus\]|\[Outro\])", raw_lyrics)
    if match:
        start_index = match.start()
        clean_lyrics = raw_lyrics[start_index:].strip()
    else:
        clean_lyrics = raw_lyrics.strip()

    return await callback.edit_message_text(clean_lyrics, reply_markup=buttons)


async def apkinfocb(_, callback_query):
    data = callback_query.data.split("_")
    page = int(data[1])
    uniq = str(data[2])
    result = state.get(uniq, uniq)
    if not result:
        await callback_query.answer(
            "Tidak ada halaman untuk ditampilkan.", show_alert=True
        )
        return
    total_result = len(result)
    if page < 0 or page >= total_result:
        await callback_query.answer("Halaman tidak ditemukan.", show_alert=True)
        return
    title = result[page].get("title")
    link = result[page].get("link")
    thumbnail = result[page].get("image")
    type = result[page].get("type")
    developer = result[page].get("developer")
    rating = result[page]["rating"]
    msg = f"""
**Title:** {title}
**Developer:** {developer}
**Rating:** {rating.get('value', '-')} | {rating.get('percentage', '-')}%
**Type:** {type}
"""
    buttons = []
    nav_buttons = []
    buttons.append([Ikb("📮 Link", url=link)])
    if page > 0:
        nav_buttons.append(Ikb("⬅️ Prev", callback_data=f"apkinfocb_{page - 1}_{uniq}"))
    if page < total_result - 1:
        nav_buttons.append(Ikb("➡️ Next", callback_data=f"apkinfocb_{page + 1}_{uniq}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([Ikb("❌ Close", callback_data=f"close inline_apkinfo {uniq}")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await callback_query.edit_message_media(
        media=InputMediaPhoto(media=thumbnail, caption=msg), reply_markup=reply_markup
    )
