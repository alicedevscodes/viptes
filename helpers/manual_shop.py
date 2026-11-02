import asyncio
import hashlib
import os
import re
import tempfile
import time
from datetime import datetime
from secrets import token_hex

from pyrogram import Client, raw
from pyrogram.file_id import FileType
from pyrogram.helpers import ikb
from pyrogram.enums import ButtonStyle
from pyrogram.utils import get_input_media_from_file_id
from clients import bot, alice
from config import API_ID, API_HASH, CODEQR, LOG_SELLER, OWNER_ID, SUDO_OWNERS
from database import dB
from command import payment_command as pay
from command import pay_peller as extra
from logs import logger

RESPON = {
    "pesanan_aktif": "Masih ada pesanan yang belum selesai. Kirim buktinya atau batalkan dulu, ya.",
    "id_nokos_salah": "Paket nomornya tidak tersedia.",
    "produk_salah": "Produknya tidak tersedia.",
    "stok_habis": "Stoknya habis atau sedang dipesan. Coba lagi nanti, ya.",
    "nokos_belum_siap": "Nomornya belum bisa dipesan. Coba lagi sebentar atau hubungi admin, ya.",
    "harga_manual": "Sesuai kesepakatan",
    "checkout": "Pesanan #{id}\nProduk: {item}\nTotal: {total}\n\nScan QRIS ini, lalu kirim foto bukti pembayarannya. Pesanan berlaku 30 menit.",
    "checkout_gagal": "Pesanannya belum bisa dibuka. Coba lagi sebentar, ya. Kalau tadi sudah pesan, cek /pesananku.",
    "bukti_diproses": "Buktinya sedang diproses. Tunggu sebentar, ya.",
    "pesanan_habis": "Waktu pembayarannya habis. Silakan pesan ulang.",
    "bukti_dipakai": "Foto ini sudah pernah dikirim. Kirim bukti untuk pesanan yang ini, ya.",
    "bukti_diterima": "Buktinya sudah diterima. Tunggu pesananmu diproses, ya.",
    "bukti_admin": "Bukti pembayaran #{id}\nPembeli: {buyer}\nProduk: {item}",
    "nokos": "Ini nomor kamu: {number}\n\nLogin dalam 10 menit, ya. OTP-nya dikirim lewat bot ini.",
    "netflix": "Ini akun Netflix kamu:\n{account}\n\nJangan ubah email/password, ya. Ada kendala? Klik Jawab Pesan.",
    "manual": "Pesanan {item} sedang diproses. Tunggu balasan admin, ya.",
    "invoice": "🧾 BUKTI PEMBELIAN\n\nPesanan: VIP-{id}\nProduk: {item}\nPembeli: {buyer}\nTotal: {total}\nTanggal: {date}\nStatus: {status}\n\nTerima kasih sudah belanja!",
    "admin_saja": "Tombol ini khusus admin.",
    "pesanan_hilang": "Pesanannya tidak ditemukan.",
    "belum_selesai": "Pesanannya masih diproses. Tunggu sebentar, ya.",
    "sudah_selesai": "Pesanan ini sudah selesai.",
    "selesai": "Pesanan selesai. Terima kasih sudah belanja!",
    "bind_format": "Nomor stok dicocokkan otomatis saat dipesan. Kamu tidak perlu memakai perintah ini.",
    "bind_belum_aktif": "Nomornya belum aktif. Hubungkan akun stoknya dulu, ya.",
    "bind_belum_stok": "Tambahkan nomor ini ke stok dulu, ya.",
    "bind_dipesan": "Nomor ini sudah dipesan atau terjual.",
    "bind_berhasil": "Nomor stok sudah aktif.",
    "otp": "Kode OTP pesanan #{id}: {code}\nJangan bagikan kode ini.",
    "bantuan_owner": "Pesanan #{id} perlu bantuanmu. Coba periksa pesanan ini, ya.",
}
LOCK = asyncio.Lock()
TESTIMONI_ID = LOG_SELLER
CHAT_KINDS = frozenset({"nf", "st", "tp"})
_BOOK = None
_TASK = None
_APPS = {}


def phone(value):
    digits = re.sub(r"\D", "", str(value))
    return "62" + digits[1:] if digits.startswith("0") else digits


async def load():
    global _BOOK
    if _BOOK is None:
        _BOOK = await dB.get_var(OWNER_ID, "MANUAL_SHOP_V1") or {"orders": {}, "sessions": {}}
    return _BOOK


async def save():
    await dB.set_var(OWNER_ID, "MANUAL_SHOP_V1", _BOOK)


def rid(key):
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") & ((1 << 63) - 1)


async def send(target, text, key, photo_id=None, markup=None):
    args = dict(peer=await bot.resolve_peer(target), message=text, random_id=rid(key))
    if markup:
        args["reply_markup"] = await markup.write(bot)
    request = raw.functions.messages.SendMessage(**args) if not photo_id else raw.functions.messages.SendMedia(
        media=get_input_media_from_file_id(photo_id, FileType.PHOTO), **args)
    return await bot.invoke(request)


def done_button(oid):
    return ikb([
        [("Transaksi Selesai", f"shopdone:{oid}", ButtonStyle.SUCCESS)],
    ])


def is_shop_admin(user_id):
    return user_id == OWNER_ID or user_id in SUDO_OWNERS


def chat_buyer_buttons(order):
    if order["kind"] not in CHAT_KINDS or order.get("chat_closed"):
        return None
    return ikb([
        [("Jawab Pesan", f"shopchat:buyer:{order['id']}", ButtonStyle.SUCCESS)],
    ])


def chat_log_buttons(order):
    if order["kind"] not in CHAT_KINDS:
        return done_button(order["id"])
    return ikb([
        [("User", f"shopchat:user:{order['id']}", ButtonStyle.PRIMARY), ("Jawab Pesan", f"shopchat:admin:{order['id']}", ButtonStyle.SUCCESS)],
        [("Transaksi Selesai", f"shopdone:{order['id']}", ButtonStyle.SUCCESS)],
    ])


def _result_message_id(result):
    direct = getattr(result, "id", None)
    if isinstance(direct, int):
        return direct
    for update in getattr(result, "updates", []) or []:
        message = getattr(update, "message", None)
        if isinstance(getattr(message, "id", None), int):
            return message.id
    return None


def active(book, uid):
    return next((o for o in book["orders"].values() if o["buyer"] == uid and o["state"] in ("awaiting_photo", "proof", "logged")), None)


async def inventory(kind, key):
    return await extra.nf_list() if kind == "nf" else await pay.get_nokos_list(key)


async def _nokos_client(number):
    number = phone(number)
    book = await load()
    binding = book["sessions"].get(number) or {}
    app = _APPS.get(number)
    if app and not getattr(app, "is_connected", False):
        _APPS.pop(number, None)
        app = None
    if app is None:
        if not binding.get("session"):
            raise ValueError("Sesi nomor stok belum tersedia.")
        app = Client(
            f"nokos-{number}", api_id=API_ID, api_hash=API_HASH,
            session_string=binding["session"], in_memory=True,
        )
        try:
            await app.connect()
            me = await app.get_me()
            if phone(me.phone_number) != number:
                raise ValueError("Nomor sesi tidak cocok dengan stok.")
        except BaseException:
            if getattr(app, "is_connected", False):
                await app.disconnect()
            raise
        _APPS[number] = app
    return app


async def _ready_nokos(number):
    number = phone(number)
    book = await load()
    binding = book["sessions"].get(number) or {}
    app = next((a for a in list(alice._ubot)
                if getattr(a, "me", None)
                and phone(getattr(a.me, "phone_number", "")) == number
                and getattr(a, "is_connected", False)), None)
    if app:
        allowed = await dB.get_var(app.me.id, "nokos_setup_enabled")
        if not allowed and not binding.get("session"):
            raise ValueError("Sesi ini belum diberi izin sebagai akun stok.")
        me = await app.get_me()
        if phone(me.phone_number) != number:
            raise ValueError("Nomor sesi tidak cocok dengan stok.")
        latest = [m.id async for m in app.get_chat_history(777000, limit=1)]
        book["sessions"][number] = {
            "session": await app.export_session_string(),
            "baseline": latest[0] if latest else 0,
            "account_id": me.id,
            "ready": False,
        }
        await save()
        await dB.remove_ubot(me.id)
        await app.stop()
        if app in alice._ubot:
            alice._ubot.remove(app)
        if me.id in alice._get_my_id:
            alice._get_my_id.remove(me.id)
        await dB.set_var(bot.id, "total_users", len(alice._ubot))
    elif not binding.get("session"):
        raise ValueError("Nomor stok belum mempunyai sesi login aktif.")
    app = await _nokos_client(number)
    binding = book["sessions"][number]
    if "baseline" not in binding:
        latest = [m.id async for m in app.get_chat_history(777000, limit=1)]
        binding["baseline"] = latest[0] if latest else 0
    binding["ready"] = True
    await save()
    return True


async def create(uid, kind, key):
    book = await load()
    if active(book, uid) or uid in pay.transactions:
        raise ValueError(RESPON["pesanan_aktif"])
    if kind == "nk":
        if key not in pay.NOKOS_IDS:
            raise ValueError(RESPON["id_nokos_salah"])
        name, amount = f"Nokos {pay.nokos_label(key).strip()}", pay.get_nokos_price(key)
    elif kind in ("nf", "tp", "st"):
        name, amount = extra.item_info(kind, key)
    elif kind == "gc":
        name, amount = "Suntik GC/CH", None
    else:
        raise ValueError(RESPON["produk_salah"])
    stock = None
    if kind in ("nk", "nf"):
        used = {
            phone(o.get("stock")) if kind == "nk" else o.get("stock")
            for o in book["orders"].values()
            if o["kind"] == kind and o["state"] != "cancelled"
        }
        reserved = (
            {phone(value) for value in pay.reserved_nokos}
            if kind == "nk" else set(extra.nf_reserved)
        )
        available = await inventory(kind, key)
        candidates = [
            value for value in available
            if (phone(value) if kind == "nk" else value) not in used | reserved
        ]
        if not candidates:
            raise ValueError(RESPON["stok_habis"])
        if kind == "nf":
            stock = candidates[0]
        else:
            for value in candidates:
                try:
                    await _ready_nokos(value)
                    stock = value
                    break
                except Exception as error:
                    logger.warning("Sesi stok belum siap: %s", type(error).__name__)
            if stock is None:
                raise ValueError(RESPON["nokos_belum_siap"])
    oid = token_hex(6)
    order = {
        "id": oid, "buyer": uid, "kind": kind, "key": key,
        "name": name, "amount": amount, "stock": stock,
        "created": time.time(), "state": "awaiting_photo",
        "testimoni": TESTIMONI_ID, "invoice_sent": False,
    }
    book["orders"][oid] = order
    await save()
    if kind == "nk":
        pay.reserved_nokos[stock] = uid
    elif kind == "nf":
        extra.nf_reserved[stock] = uid
    return order


async def checkout(client, query, kind, key):
    try:
        async with LOCK:
            order = await create(query.from_user.id, kind, key)
        await query.answer()
        amount = RESPON["harga_manual"] if order["amount"] is None else f"Rp{order['amount']:,}".replace(",", ".")
        caption = RESPON["checkout"].format(id=order["id"], item=order["name"], total=amount)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "qris.png")
            await pay.make_qr_image(CODEQR, path)
            await client.send_photo(order["buyer"], path, caption=caption, reply_markup=ikb([
                [("Batalkan", "batal_payment", ButtonStyle.DANGER)],
            ]))
    except ValueError as error:
        await query.answer(str(error)[:190], show_alert=True)
    except Exception:
        await client.send_message(query.from_user.id, RESPON["checkout_gagal"])


async def accept_photo(message):
    async with LOCK:
        book = await load()
        order = active(book, message.from_user.id)
        if not order:
            return False
        if order["state"] != "awaiting_photo":
            await message.reply(RESPON["bukti_diproses"], reply_markup=chat_buyer_buttons(order))
            return True
        if time.time() - order["created"] >= 1800:
            await cancel(order)
            await message.reply(RESPON["pesanan_habis"])
            return True
        unique = message.photo.file_unique_id
        if any(o.get("proof_unique") == unique for o in book["orders"].values()):
            await message.reply(RESPON["bukti_dipakai"])
            return True
        order.update(state="proof", proof=message.photo.file_id, proof_unique=unique, proof_at=time.time())
        await save()
    await message.reply(RESPON["bukti_diterima"], reply_markup=chat_buyer_buttons(order))
    return True


async def cancel(order):
    order["state"] = "cancelled"
    if order["kind"] == "nk":
        pay.release_nokos(order.get("stock"))
    elif order["kind"] == "nf":
        extra.nf_reserved.pop(order.get("stock"), None)
    await save()


async def fulfil(order):
    oid, uid = order["id"], order["buyer"]
    if order["state"] == "proof":
        result = await send(
            LOG_SELLER, RESPON["bukti_admin"].format(id=oid, buyer=uid, item=order["name"]),
            f"{oid}:proof", photo_id=order["proof"], markup=chat_log_buttons(order),
        )
        order["log_message_id"] = _result_message_id(result)
        order["state"] = "logged"
        await save()
    if order["state"] != "logged":
        return
    kind = order["kind"]
    if kind == "nk":
        await pay.sell_nokos(order["key"], order["stock"])
        text = RESPON["nokos"].format(number=order["stock"])
    elif kind == "nf":
        await extra.nf_sell(order["stock"])
        text = RESPON["netflix"].format(account=order["stock"])
    else:
        text = RESPON["manual"].format(item=order["name"])
    if not order.get("delivery_at"):
        order["delivery_at"] = time.time()
        await save()
    await send(uid, text, f"{oid}:delivery", markup=chat_buyer_buttons(order))
    order.update(state="delivered" if kind in ("nk", "nf") else "waiting_owner", invoice_due=order["delivery_at"] + 1800)
    await save()


def invoice(order, now=None):
    date = datetime.fromtimestamp(order.get("delivery_at", order["created"]), pay.waktu_jkt).strftime("%d-%m-%Y %H:%M WIB")
    total = RESPON["harga_manual"] if order["amount"] is None else f"Rp{order['amount']:,}".replace(",", ".")
    if order.get("completed_by"):
        status = "Selesai"
    elif order["state"] == "delivered":
        status = "Sudah dikirim"
    else:
        status = "Sedang diproses admin"
    return RESPON["invoice"].format(
        id=order["id"].upper(), item=order["name"], buyer=str(order["buyer"])[:3] + "***",
        total=total, date=date, status=status,
    )


async def publish(order):
    if order.get("invoice_sent"):
        return
    if "invoice_text" not in order:
        order["invoice_text"] = invoice(order)
        await save()
    await send(order["testimoni"], order["invoice_text"], f"{order['id']}:invoice")
    order["invoice_sent"] = True
    await save()


async def finish(query):
    if (not is_shop_admin(query.from_user.id) or not query.message
            or query.message.chat.id != LOG_SELLER):
        return await query.answer(RESPON["admin_saja"], show_alert=True)
    oid = query.data.split(":", 1)[1]
    async with LOCK:
        order = (await load())["orders"].get(oid)
        if not order:
            return await query.answer(RESPON["pesanan_hilang"], show_alert=True)
        if order["state"] not in ("delivered", "waiting_owner"):
            return await query.answer(RESPON["belum_selesai"], show_alert=True)
        if order.get("chat_closed"):
            return await query.answer(RESPON["sudah_selesai"], show_alert=True)
        order.update(chat_closed=True, completed_by="owner", completed_admin=query.from_user.id,
                     completed_at=time.time(), invoice_due=time.time())
        await save()
        try:
            await query.answer(RESPON["selesai"])
        except Exception:
            pass
        if not order.get("invoice_sent"):
            try:
                await publish(order)
            except Exception:
                logger.exception("Invoice belum terkirim; worker akan mencoba kembali")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


async def bind(message):
    if message.from_user.id != OWNER_ID or message.chat.id != OWNER_ID:
        return
    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply(RESPON["bind_format"])
    number, uid = phone(parts[1]), int(parts[2])
    from clients import alice
    app = next((a for a in alice._ubot if a.me.id == uid and phone(a.me.phone_number) == number), None)
    if not app:
        return await message.reply(RESPON["bind_belum_aktif"])
    async with LOCK:
        book = await load()
        stock = [n for key in pay.NOKOS_IDS for n in await pay.get_nokos_list(key)]
        if number not in {phone(n) for n in stock}:
            return await message.reply(RESPON["bind_belum_stok"])
        if any(o["kind"] == "nk" and phone(o.get("stock") or "") == number and o["state"] != "cancelled" for o in book["orders"].values()):
            return await message.reply(RESPON["bind_dipesan"])
        latest = [m.id async for m in app.get_chat_history(777000, limit=1)]
        book["sessions"][number] = {"session": await app.export_session_string(), "baseline": latest[0] if latest else 0, "ready": False}
        await save()
        await dB.remove_ubot(uid)
        await app.stop()
        if app in alice._ubot:
            alice._ubot.remove(app)
        if uid in alice._get_my_id:
            alice._get_my_id.remove(uid)
        await dB.set_var(bot.id, "total_users", len(alice._ubot))
        book["sessions"][number]["ready"] = True
        await save()
    await message.reply(RESPON["bind_berhasil"])


async def otp(order):
    number = phone(order["stock"])
    book = await load()
    if order.get("otp_sent") or time.time() > order["delivery_at"] + 600:
        app = _APPS.pop(number, None)
        if app:
            await app.disconnect()
        changed = book["sessions"].pop(number, None) is not None
        if order.pop("otp_code", None) is not None:
            changed = True
        if changed:
            await save()
        return
    binding = book["sessions"].get(number)
    if not binding:
        raise ValueError("Sesi OTP pesanan tidak tersedia.")
    app = await _nokos_client(number)
    if not order.get("otp_code"):
        messages = [m async for m in app.get_chat_history(777000, limit=10)]
        for message in reversed(messages):
            match = re.search(
                r"(?i)(?:login code|kode login|kode masuk|telegram code)\D{0,30}(\d{5})\b",
                message.text or "",
            )
            if (match and message.id > binding.get("baseline", 0)
                    and message.date.timestamp() >= order["delivery_at"]):
                order.update(otp_code=match.group(1), otp_message_id=message.id)
                await save()
                break
    if order.get("otp_code"):
        await send(order["buyer"], RESPON["otp"].format(id=order["id"], code=order["otp_code"]), f"{order['id']}:otp")
        order["otp_sent"] = True
        order.pop("otp_code", None)
        await save()


async def worker():
    await asyncio.sleep(2)
    try:
        while True:
            async with LOCK:
                book = await load()
                for order in list(book["orders"].values()):
                    try:
                        if order["state"] == "awaiting_photo" and time.time() - order["created"] >= 1800:
                            await cancel(order)
                        if order["state"] in ("proof", "logged"):
                            await fulfil(order)
                        if order["state"] in ("delivered", "waiting_owner") and time.time() >= order.get("invoice_due", float("inf")):
                            await publish(order)
                        if order["state"] == "delivered" and order["kind"] == "nk":
                            await otp(order)
                    except Exception as error:
                        logger.warning("Pesanan %s gagal pada tahap %s: %s", order["id"], order["state"], type(error).__name__)
                        if not order.get("error_notified"):
                            try:
                                await bot.send_message(OWNER_ID, RESPON["bantuan_owner"].format(id=order["id"]))
                            except Exception:
                                pass
                            order["error_notified"] = True
                            await save()
            await asyncio.sleep(10)
    finally:
        for app in list(_APPS.values()):
            try:
                await app.disconnect()
            except Exception:
                pass
        _APPS.clear()


def start_worker():
    global _TASK
    if _TASK is None or _TASK.done():
        _TASK = asyncio.create_task(worker())
