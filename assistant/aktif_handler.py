import asyncio
from datetime import datetime

from pyrogram import StopPropagation, filters
from pyrogram.enums import ParseMode
from pytz import timezone

from clients import bot
from command.addubot_command import (
    SETUP_OTP_BUTTON,
    mari_buat_userbot,
    setExpiredUser,
    setup_otp_keyboard,
)
from config import AKSES_DEPLOY, OWNER_ID
from database import dB

_AKTIF_LOCK = asyncio.Lock()
_TZ = timezone("Asia/Jakarta")


@bot.on_message(
    filters.private & filters.user(OWNER_ID) & filters.command("aktif"),
    group=-30,
)
async def aktif_handler(client, message):
    try:
        args = message.text.split()
        if len(args) != 2 or not args[1].isdigit():
            return await message.reply(
                "Format: <code>/aktif USER_ID</code>\n"
                "Contoh: <code>/aktif 8713820679</code>",
                parse_mode=ParseMode.HTML,
            )

        user_id = int(args[1])
        if user_id <= 0 or user_id == client.me.id:
            return await message.reply("ID akun tidak valid.")

        async with _AKTIF_LOCK:
            expired = await dB.get_expired_date(user_id)
            if not expired or expired <= datetime.now(_TZ):
                await setExpiredUser(user_id)
                expired = await dB.get_expired_date(user_id)

            await dB.set_var(user_id, "plan", "is_pro")
            if user_id not in AKSES_DEPLOY:
                AKSES_DEPLOY.append(user_id)

        batas = expired.astimezone(_TZ).strftime("%d-%m-%Y %H:%M WIB")
        notified = True
        try:
            await client.send_message(
                user_id,
                "<b>✅ Akses database OTP nokos telah diaktifkan.</b>\n\n"
                f"ID akun: <code>{user_id}</code>\n"
                f"Berlaku sampai: <code>{batas}</code>\n\n"
                "Silakan lanjutkan setup untuk menambahkan akun stok milikmu.\n"
                "Tahap berikutnya melakukan login Telegram dan menautkan "
                "sesi akun ke sistem.",
                parse_mode=ParseMode.HTML,
                reply_markup=setup_otp_keyboard(),
            )
        except Exception:
            notified = False

        text = (
            "<b>✅ Akses database OTP nokos berhasil diaktifkan.</b>\n\n"
            f"ID akun: <code>{user_id}</code>\n"
            f"Berlaku sampai: <code>{batas}</code>\n\n"
            "Akun dapat melanjutkan setup melalui bot."
        )
        if not notified:
            text += (
                "\nNotifikasi belum terkirim. Akses tetap tersimpan; "
                "buka /start dari akun tersebut dahulu."
            )
        await message.reply(text, parse_mode=ParseMode.HTML)
    finally:
        raise StopPropagation


@bot.on_message(
    filters.private & ~filters.bot
    & filters.regex(r"^📲 Lanjutkan Setup OTP Nokos$"),
    group=-29,
)
async def lanjut_setup_otp(client, message):
    try:
        await mari_buat_userbot(client, message)
    finally:
        raise StopPropagation