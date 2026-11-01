import asyncio
import importlib
from datetime import datetime
from html import escape

import hydrogram
from dateutil.relativedelta import relativedelta
from pyrogram.helpers import kb
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from pytz import timezone

from clients import UserBot, bot, alice
from config import (
    AKSES_DEPLOY, API_HASH, API_ID, BOT_ID,
    LOG_SELLER, MAX_BOT, SUDO_OWNERS, WAJIB_JOIN,
)
from database import dB, state
from helpers import TokenReferal, no_trigger
from logs import logger
from plugins import PLUGINS

SETUP_OTP_BUTTON = "📲 Lanjutkan Setup OTP Nokos"
_SETUP_PENDING = set()
_TZ = timezone("Asia/Jakarta")


def setup_otp_keyboard():
    return kb(
        [[SETUP_OTP_BUTTON]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _cancelled(message):
    text = (message.text or "").strip()
    return text in no_trigger or text.lower() in ("/cancel", "cancel", "batal")


async def _cancel_setup(client, user_id):
    return await client.send_message(
        user_id,
        "<b>Setup database OTP nokos dibatalkan.</b>\n"
        "Silakan lanjutkan kembali saat akun stok sudah siap.",
        reply_markup=setup_otp_keyboard(),
    )


async def setExpiredUser(user_id):
    months = 12 if user_id in SUDO_OWNERS else 1
    expired = datetime.now(_TZ) + relativedelta(months=months)
    await dB.set_expired_date(user_id, expired)


async def mari_buat_userbot(client, message):
    user_id = message.from_user.id
    if user_id in _SETUP_PENDING:
        return await message.reply(
            "Setup akun ini sedang berjalan. Selesaikan atau batalkan proses sebelumnya."
        )

    if any(app.me.id == user_id for app in alice._ubot):
        return await message.reply(
            "<b>Sesi akun sudah terhubung.</b>\n"
            "Owner dapat melanjutkan pengikatan nomor melalui "
            "<code>/bindnokos NOMOR USER_ID</code>."
        )

    if len(alice._ubot) >= MAX_BOT:
        return await message.reply(
            "<b>Kapasitas akun terhubung sedang penuh.</b>\n"
            "Hubungi owner sebelum menambahkan akun stok berikutnya.",
            reply_markup=ReplyKeyboardRemove(),
        )

    expired = await dB.get_expired_date(user_id)
    if expired and datetime.now(_TZ) >= expired:
        return await message.reply(
            "<b>Akses setup database OTP nokos sudah berakhir.</b>\n"
            "Hubungi owner untuk mengaktifkan kembali akses akun ini.",
            reply_markup=ReplyKeyboardRemove(),
        )

    if not expired and user_id not in AKSES_DEPLOY:
        return await message.reply(
            "<b>Akses setup database OTP nokos belum aktif.</b>\n\n"
            f"ID akun: <code>{user_id}</code>\n"
            "Minta owner mengaktifkan akun ini melalui:\n"
            f"<code>/aktif {user_id}</code>",
            reply_markup=ReplyKeyboardRemove(),
        )

    _SETUP_PENDING.add(user_id)
    try:
        return await create_userbots(client, message)
    finally:
        _SETUP_PENDING.discard(user_id)


async def create_userbots(client, message):
    user_id = message.from_user.id
    new_client = None
    kn_client = None
    otp_message = None
    password_message = None

    try:
        tokenref = await TokenReferal.create()
        try:
            referral = await client.ask(
                user_id,
                "<b>Persiapan database OTP nokos</b>\n\n"
                "Proses berikut melakukan login Telegram dan membuat sesi "
                "akses akun untuk sistem. Gunakan hanya akun stok milikmu sendiri.\n\n"
                "Masukkan kode referral jika tersedia, atau ketik "
                "<code>skip</code> untuk melanjutkan.\n"
                "Ketik <code>/cancel</code> untuk membatalkan.",
                timeout=300,
            )
            if _cancelled(referral):
                return await _cancel_setup(client, user_id)

            referral_text = (referral.text or "").strip()
            kode_referal = (
                None if referral_text.lower() in ("", "skip", "/skip")
                else referral_text
            )
        except asyncio.TimeoutError:
            return await client.send_message(
                user_id,
                "Waktu persiapan habis. Silakan mulai setup kembali.",
                reply_markup=setup_otp_keyboard(),
            )

        contact_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Kirim Nomor Akun Stok", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        phone_message = await client.ask(
            user_id,
            "<b>Tambahkan akun stok nokos</b>\n\n"
            "Tekan tombol di bawah untuk mengirim nomor akun Telegram ini.\n"
            "Nomor harus milik akun yang sedang membuka bot.\n\n"
            "Ketik <code>/cancel</code> untuk membatalkan.",
            reply_markup=contact_keyboard,
            timeout=300,
        )

        if _cancelled(phone_message):
            return await _cancel_setup(client, user_id)

        contact = phone_message.contact
        if not contact or contact.user_id != user_id:
            return await client.send_message(
                user_id,
                "<b>Nomor belum dapat diproses.</b>\n"
                "Gunakan tombol Kirim Nomor Akun Stok dari akunmu sendiri, "
                "bukan kontak yang diteruskan.",
                reply_markup=setup_otp_keyboard(),
            )

        phone_number = contact.phone_number.strip()
        new_client = hydrogram.Client(
            name=str(user_id),
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True,
        )
        await client.send_message(
            user_id,
            "<b>Mengirim kode verifikasi Telegram ke akun stok...</b>\n"
            "Kode ini digunakan untuk menautkan sesi akun ke sistem.",
            reply_markup=ReplyKeyboardRemove(),
        )

        await new_client.connect()
        code = await new_client.send_code(phone_number)
        otp_message = await client.ask(
            user_id,
            "<b>Verifikasi akun stok nokos</b>\n\n"
            "Periksa kode login dari akun Telegram resmi "
            "<a href='tg://openmessage?user_id=777000'>777000</a>.\n"
            "Masukkan kode untuk menyetujui penautan sesi akun milikmu.\n\n"
            "Contoh format: <code>1 2 3 4 5</code>\n"
            "Ketik <code>/cancel</code> untuk membatalkan.",
            timeout=300,
        )
        if _cancelled(otp_message):
            return await _cancel_setup(client, user_id)

        otp_code = "".join((otp_message.text or "").split())
        if not otp_code.isdigit():
            return await client.send_message(
                user_id,
                "Format kode verifikasi tidak valid. Mulai setup kembali.",
                reply_markup=setup_otp_keyboard(),
            )

        try:
            await new_client.sign_in(
                phone_number,
                code.phone_code_hash,
                phone_code=otp_code,
            )
        except hydrogram.errors.exceptions.unauthorized_401.SessionPasswordNeeded:
            password_message = await client.ask(
                user_id,
                "<b>Verifikasi dua langkah aktif.</b>\n\n"
                "Masukkan password dua langkah akun stok milikmu "
                "untuk menyelesaikan login Telegram.\n"
                "Password tidak disimpan oleh fungsi setup ini.\n\n"
                "Ketik <code>/cancel</code> untuk membatalkan.",
                timeout=300,
            )
            if _cancelled(password_message):
                return await _cancel_setup(client, user_id)
            await new_client.check_password(password_message.text or "")

        account = await new_client.get_me()
        if account.id != user_id:
            await new_client.log_out()
            return await client.send_message(
                user_id,
                "<b>Akun tidak cocok.</b>\n"
                "Buka bot menggunakan akun stok yang sama dengan nomor login.",
                reply_markup=setup_otp_keyboard(),
            )

        session_string = await new_client.export_session_string()
        await new_client.disconnect()
        await client.send_message(
            user_id,
            "<b>Verifikasi berhasil.</b>\n"
            "Sedang menghubungkan sesi akun untuk persiapan database OTP nokos...",
        )

        kn_client = UserBot(
            name=str(user_id),
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_string,
            in_memory=True,
        )
        await kn_client.start()
        for module in PLUGINS:
            importlib.reload(importlib.import_module(f"plugins.{module}"))

        if not await dB.get_expired_date(user_id):
            await setExpiredUser(user_id)

        await dB.add_ubot(user_id=user_id, session_string=session_string)
        await dB.set_var(bot.id, "total_users", len(alice._ubot))

        referral = await tokenref.register_user(
            user_id=str(user_id),
            phone=phone_number,
            referral_code=kode_referal,
        )

        sellers = await dB.get_list_from_var(BOT_ID, "SELLER")
        if user_id not in sellers and user_id in AKSES_DEPLOY:
            AKSES_DEPLOY.remove(user_id)

        for chat in WAJIB_JOIN:
            try:
                await kn_client.join_chat(chat)
            except Exception:
                pass

        expired = await dB.get_expired_date(user_id)
        batas = expired.astimezone(_TZ).strftime("%d-%m-%Y %H:%M WIB")
        token = escape(str(referral.get("token") or "-"))

        await client.send_message(
            user_id,
            "<b>✅ Sesi akun stok berhasil terhubung.</b>\n\n"
            f"ID akun: <code>{user_id}</code>\n"
            f"Akses berlaku sampai: <code>{batas}</code>\n"
            f"Token pengelolaan: <code>{token}</code>\n\n"
            "<b>Langkah berikutnya:</b>\n"
            "Owner menambahkan nomor ke stok, kemudian mengikat sesi dengan:\n"
            f"<code>/bindnokos {escape(phone_number)} {user_id}</code>\n\n"
            "Relay OTP untuk pembeli baru siap setelah pengikatan berhasil. "
            "Simpan token pengelolaan secara pribadi.",
            reply_markup=ReplyKeyboardRemove(),
        )

        seller = state.get(user_id, "seller")
        if seller:
            count = await dB.get_var(int(seller), "penjualan") or 0
            await dB.set_var(int(seller), "penjualan", count + 1)

        await client.send_message(
            LOG_SELLER,
            "<b>📲 Akun stok siap ditautkan ke database OTP nokos</b>\n"
            f"ID akun: <code>{user_id}</code>\n"
            "Status: sesi terhubung, menunggu pengikatan melalui /bindnokos.",
        )

    except asyncio.TimeoutError:
        await client.send_message(
            user_id,
            "Waktu verifikasi habis. Silakan ulangi setup database OTP nokos.",
            reply_markup=setup_otp_keyboard(),
        )
    except Exception as error:
        logger.error(f"Setup akun stok gagal: {type(error).__name__}")
        text = (
            "Setup belum selesai. Sesi akun mungkin sudah terhubung; "
            "owner perlu memeriksa status sebelum mencoba ulang."
            if kn_client and getattr(kn_client, "is_connected", False)
            else "Setup belum berhasil. Periksa nomor dan kode verifikasi, lalu coba kembali."
        )
        await client.send_message(
            user_id,
            text,
            reply_markup=setup_otp_keyboard(),
        )
    finally:
        for sensitive_message in (otp_message, password_message):
            if sensitive_message:
                try:
                    await sensitive_message.delete()
                except Exception:
                    pass
        if new_client and getattr(new_client, "is_connected", False):
            try:
                await new_client.disconnect()
            except Exception:
                pass