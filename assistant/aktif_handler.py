import asyncio
from datetime import datetime

from pyrogram import StopPropagation, filters
from pyrogram.enums import ParseMode
from pytz import timezone

from clients import bot
from command.addubot_command import buyer_menu, mari_buat_userbot, setExpiredUser, setup_otp_keyboard
from config import AKSES_DEPLOY, OWNER_ID
from database import dB
from logs import logger

RESPON = {
    "format": "Contoh: <code>/aktif 8713820679</code>",
    "id_salah": "ID akunnya tidak valid.",
    "aktif_user": "<b>Akses OTP nokos sudah aktif.</b>\n\nID: <code>{id}</code>\nBerlaku sampai: <code>{batas}</code>\n\nKlik tombol di bawah untuk menghubungkan akun Telegram milikmu.",
    "aktif_owner": "<b>Akses OTP nokos berhasil diaktifkan.</b>\n\nID: <code>{id}</code>\nBerlaku sampai: <code>{batas}</code>",
    "notif_gagal": "\n\nPemberitahuan belum terkirim. Buka /start dari akun tersebut, ya.",
    "gagal": "Belum bisa diaktifkan. Coba lagi sebentar, ya.",
    "menu_gagal": "Menunya belum bisa dibuka. Coba lagi, ya.",
}

_AKTIF_LOCK = asyncio.Lock()
_TZ = timezone("Asia/Jakarta")
_BUY_BUTTONS = {"Beli Seblak Bang", "🛒 Beli Produk"}
_ENTRY_PATTERN = (
    r"^(?:Beli Seblak Bang|🛒 Beli Produk|"
    r"📲 Lanjutkan Setup OTP Nokos|"
    r"✅ Lanjutkan Buat Userbot|"
    r"✨ Pembuatan Ulang Userbot)$"
)


@bot.on_message(filters.private & filters.user(OWNER_ID) & filters.command("aktif"), group=-40)
async def aktif_handler(client, message):
    try:
        args = message.text.split()
        if len(args) != 2 or not args[1].isdigit():
            return await message.reply(RESPON["format"], parse_mode=ParseMode.HTML)
        user_id = int(args[1])
        if user_id <= 0 or user_id == client.me.id:
            return await message.reply(RESPON["id_salah"])
        async with _AKTIF_LOCK:
            expired = await dB.get_expired_date(user_id)
            if not expired or expired <= datetime.now(_TZ):
                await setExpiredUser(user_id)
                expired = await dB.get_expired_date(user_id)
            await dB.set_var(user_id, "plan", "is_pro")
            await dB.set_var(user_id, "nokos_setup_enabled", True)
            if user_id not in AKSES_DEPLOY:
                AKSES_DEPLOY.append(user_id)
        batas = expired.astimezone(_TZ).strftime("%d-%m-%Y %H:%M WIB")
        notified = True
        try:
            await client.send_message(
                user_id, RESPON["aktif_user"].format(id=user_id, batas=batas),
                parse_mode=ParseMode.HTML, reply_markup=setup_otp_keyboard(),
            )
        except Exception:
            notified = False
        text = RESPON["aktif_owner"].format(id=user_id, batas=batas)
        if not notified:
            text += RESPON["notif_gagal"]
        await message.reply(text, parse_mode=ParseMode.HTML)
    except Exception:
        logger.exception("Aktivasi akses setup OTP nokos gagal")
        await message.reply(RESPON["gagal"])
    finally:
        raise StopPropagation


@bot.on_message(filters.private & ~filters.bot & filters.regex(_ENTRY_PATTERN), group=-40)
async def route_buyer_or_setup(client, message):
    try:
        user_id = message.from_user.id
        banned = await dB.get_list_from_var(client.me.id, "BANNED_USERS") or []
        if user_id in banned:
            return
        text = (message.text or "").strip()
        if text in _BUY_BUTTONS:
            return await buyer_menu(client, message)
        if not await dB.get_var(user_id, "nokos_setup_enabled"):
            return await buyer_menu(client, message)
        return await mari_buat_userbot(client, message)
    except Exception:
        logger.exception("Routing pembelian/setup OTP gagal")
        await message.reply(RESPON["menu_gagal"])
    finally:
        raise StopPropagation
