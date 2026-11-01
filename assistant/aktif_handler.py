import asyncio
from datetime import datetime

from pyrogram import StopPropagation, filters
from pyrogram.enums import ParseMode
from pyrogram.helpers import kb
from pytz import timezone

from clients import bot
from command.addubot_command import setExpiredUser
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
        notification_sent = True
        try:
            await client.send_message(
                user_id,
                "<b>Akses userbot sudah diaktifkan.</b>\n\n"
                f"ID: <code>{user_id}</code>\n"
                "Plan: <b>Pro</b>\n"
                f"Berlaku sampai: <code>{batas}</code>\n\n"
                "Tekan tombol di bawah untuk melanjutkan login akunmu.",
                parse_mode=ParseMode.HTML,
                reply_markup=kb(
                    [["✅ Lanjutkan Buat Userbot"]],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )
        except Exception:
            notification_sent = False

        text = (
            "<b>Akses userbot berhasil diberikan.</b>\n\n"
            f"ID akun: <code>{user_id}</code>\n"
            "Plan: <b>Pro</b>\n"
            f"Berlaku sampai: <code>{batas}</code>"
        )
        if not notification_sent:
            text += (
                "\n\nNotifikasi belum berhasil dikirim. "
                "Akses tetap tersimpan; buka /start dari akun tersebut."
            )
        await message.reply(text, parse_mode=ParseMode.HTML)
    finally:
        raise StopPropagation