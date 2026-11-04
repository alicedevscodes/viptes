import asyncio
import importlib
from datetime import datetime
from html import escape

import hydrogram
from dateutil.relativedelta import relativedelta
from pyrogram.helpers import kb
from pyrogram.enums import ParseMode
from pyrogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from pytz import timezone

from clients import UserBot, bot, alice
from config import AKSES_DEPLOY, API_HASH, API_ID, BOT_ID, LOG_SELLER, MAX_BOT, SUDO_OWNERS, WAJIB_JOIN
from database import dB, state
from helpers import ButtonUtils, TokenReferal
from logs import logger
from plugins import PLUGINS

RESPON = {
    "batal": "Setup dibatalkan. Bisa dilanjutkan nanti, ya.",
    "menu": "<b>🛒 Menu produk ZanStore</b>\n\nPilih produk yang ingin kamu beli.",
    "membuka_menu": "Membuka menu...",
    "sedang_setup": "Setup sebelumnya belum selesai. Lanjutkan dulu atau ketik /cancel.",
    "sudah_aktif": "<b>Nomor stok sudah terhubung.</b>\nCukup tambahkan nomornya ke stok. Tidak perlu login ulang.",
    "penuh": "Kapasitas akun sedang penuh. Hubungi admin, ya.",
    "akses_habis": "Akses OTP nokos belum aktif atau sudah habis. Hubungi admin, ya.",
    "referral": "<b>Hubungkan akun stok</b>\n\nLogin ini menghubungkan akun Telegram milikmu ke bot untuk menerima OTP stok.\n\nPunya kode referral? Kirim di sini, atau ketik /skip.\n/cancel untuk batal.",
    "setup_habis": "Waktunya habis. Klik Lanjutkan Setup OTP Nokos untuk mencoba lagi.",
    "nomor": "Klik Kirim Nomor Akun Stok untuk mengirim nomor akun ini.\nGunakan akun stok milikmu sendiri, ya.\n/cancel untuk batal.",
    "kontak_salah": "Kirim nomornya lewat tombol Kirim Nomor Akun Stok dari akun yang sama. Coba ulangi, ya.",
    "mengirim_otp": "Mengirim kode login Telegram ke akunmu...",
    "minta_otp": "Masukkan kode login Telegram dari 777000.\nContoh: <code>1 2 3 4 5</code>\n/cancel untuk batal.",
    "otp_salah": "Kodenya belum benar. Coba ulangi setup, ya.",
    "minta_2fa": "Akun ini memakai verifikasi dua langkah. Masukkan password akun stokmu untuk login.\nPassword tidak disimpan.\n/cancel untuk batal.",
    "akun_tidak_cocok": "Nomornya tidak cocok dengan akun ini. Buka bot dari akun stok yang sama, ya.",
    "menghubungkan": "Kode benar. Sedang menghubungkan akunmu...",
    "berhasil": "<b>Nomor stok sudah terhubung.</b>\n\nID: <code>{id}</code>\nBerlaku sampai: <code>{batas}</code>\nToken: <code>{token}</code>\n\nCukup tambahkan nomor <code>{phone}</code> ke stok agar bisa dipesan. Simpan token ini baik-baik, ya.",
    "notifikasi_owner": "Nomor stok terhubung.\nID: <code>{id}</code>\nTinggal tambahkan nomornya ke stok.",
    "verifikasi_habis": "Waktu pengisian kode habis. Coba ulangi setup, ya.",
    "gagal_terhubung": "Setup belum selesai. Akunnya sudah terhubung; minta admin memeriksa dulu, ya.",
    "gagal": "Belum berhasil. Periksa nomor dan kodenya, lalu coba lagi, ya.",
}
SETUP_OTP_BUTTON = "📲 Lanjutkan Setup OTP Nokos"
_SETUP_PENDING = set()
_TZ = timezone("Asia/Jakarta")


def setup_otp_keyboard():
    return kb([[SETUP_OTP_BUTTON]], resize_keyboard=True, one_time_keyboard=True)


def _cancelled(message):
    text = getattr(message, "text", None)
    if not isinstance(text, str) or not text.strip():
        return False
    return text.strip().casefold() in {"/cancel", "cancel", "/batal", "batal", "❌ batalkan"}


async def _cancel_setup(client, user_id):
    return await client.send_message(user_id, RESPON["batal"], reply_markup=setup_otp_keyboard())


async def setExpiredUser(user_id):
    months = 12 if user_id in SUDO_OWNERS else 1
    expired = datetime.now(_TZ) + relativedelta(months=months)
    await dB.set_expired_date(user_id, expired)


async def buyer_menu(client, message):
    loading = None
    stage = "membuat keyboard katalog"
    try:
        markup = ButtonUtils.chose_plan()
        stage = "menghapus keyboard lama"
        loading = await client.send_message(message.chat.id, RESPON["membuka_menu"], reply_markup=ReplyKeyboardRemove())
        stage = "mengirim katalog beserta tombol"
        return await client.send_message(message.chat.id, RESPON["menu"], parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception:
        logger.exception("buyer_menu gagal pada tahap: %s", stage)
        raise
    finally:
        if loading:
            try:
                await loading.delete()
            except Exception:
                pass


async def mari_buat_userbot(client, message):
    user_id = message.from_user.id
    if not await dB.get_var(user_id, "nokos_setup_enabled"):
        return await buyer_menu(client, message)
    if user_id in _SETUP_PENDING:
        return await message.reply(RESPON["sedang_setup"])
    if any(app.me.id == user_id for app in alice._ubot):
        return await message.reply(RESPON["sudah_aktif"], reply_markup=ReplyKeyboardRemove())
    if len(alice._ubot) >= MAX_BOT:
        return await message.reply(RESPON["penuh"], reply_markup=ReplyKeyboardRemove())
    expired = await dB.get_expired_date(user_id)
    if not expired or datetime.now(_TZ) >= expired:
        return await message.reply(RESPON["akses_habis"], reply_markup=ReplyKeyboardRemove())
    _SETUP_PENDING.add(user_id)
    try:
        return await create_userbots(client, message)
    finally:
        _SETUP_PENDING.discard(user_id)


async def create_userbots(client, message):
    user_id = message.from_user.id
    new_client = kn_client = otp_message = password_message = None
    try:
        tokenref = await TokenReferal.create()
        try:
            referral = await client.ask(user_id, RESPON["referral"], timeout=300)
            if _cancelled(referral):
                return await _cancel_setup(client, user_id)
            referral_text = (referral.text or "").strip()
            kode_referal = None if referral_text.lower() in ("", "skip", "/skip") else referral_text
        except asyncio.TimeoutError:
            return await client.send_message(user_id, RESPON["setup_habis"], reply_markup=setup_otp_keyboard())
        contact_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Kirim Nomor Akun Stok", request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True,
        )
        phone_message = await client.ask(user_id, RESPON["nomor"], reply_markup=contact_keyboard, timeout=300)
        if _cancelled(phone_message):
            return await _cancel_setup(client, user_id)
        contact = phone_message.contact
        if not contact or contact.user_id != user_id:
            return await client.send_message(user_id, RESPON["kontak_salah"], reply_markup=setup_otp_keyboard())
        phone_number = contact.phone_number.strip()
        new_client = hydrogram.Client(name=str(user_id), api_id=API_ID, api_hash=API_HASH, in_memory=True)
        await client.send_message(user_id, RESPON["mengirim_otp"], reply_markup=ReplyKeyboardRemove())
        await new_client.connect()
        code = await new_client.send_code(phone_number)
        otp_message = await client.ask(user_id, RESPON["minta_otp"], timeout=300)
        if _cancelled(otp_message):
            return await _cancel_setup(client, user_id)
        otp_code = "".join((otp_message.text or "").split())
        if not otp_code.isdigit():
            return await client.send_message(user_id, RESPON["otp_salah"], reply_markup=setup_otp_keyboard())
        try:
            await new_client.sign_in(phone_number, code.phone_code_hash, phone_code=otp_code)
        except hydrogram.errors.exceptions.unauthorized_401.SessionPasswordNeeded:
            password_message = await client.ask(user_id, RESPON["minta_2fa"], timeout=300)
            if _cancelled(password_message):
                return await _cancel_setup(client, user_id)
            await new_client.check_password(password_message.text or "")
        account = await new_client.get_me()
        if account.id != user_id:
            await new_client.log_out()
            return await client.send_message(user_id, RESPON["akun_tidak_cocok"], reply_markup=setup_otp_keyboard())
        session_string = await new_client.export_session_string()
        await new_client.disconnect()
        await client.send_message(user_id, RESPON["menghubungkan"])
        kn_client = UserBot(name=str(user_id), api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
        await kn_client.start()
        for module in PLUGINS:
            importlib.reload(importlib.import_module(f"plugins.{module}"))
        if not await dB.get_expired_date(user_id):
            await setExpiredUser(user_id)
        await dB.add_ubot(user_id=user_id, session_string=session_string)
        await dB.set_var(bot.id, "total_users", len(alice._ubot))
        referral = await tokenref.register_user(user_id=str(user_id), phone=phone_number, referral_code=kode_referal)
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
            user_id, RESPON["berhasil"].format(id=user_id, batas=batas, token=token, phone=escape(phone_number)),
            reply_markup=ReplyKeyboardRemove(),
        )
        seller = state.get(user_id, "seller")
        if seller:
            count = await dB.get_var(int(seller), "penjualan") or 0
            await dB.set_var(int(seller), "penjualan", count + 1)
        await client.send_message(LOG_SELLER, RESPON["notifikasi_owner"].format(id=user_id))
    except asyncio.TimeoutError:
        await client.send_message(user_id, RESPON["verifikasi_habis"], reply_markup=setup_otp_keyboard())
    except Exception as error:
        logger.error("Setup akun stok gagal: %s", type(error).__name__)
        text = RESPON["gagal_terhubung"] if kn_client and getattr(kn_client, "is_connected", False) else RESPON["gagal"]
        await client.send_message(user_id, text, reply_markup=setup_otp_keyboard())
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
