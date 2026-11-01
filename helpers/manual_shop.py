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
from clients import bot
from config import API_ID, API_HASH, CODEQR, LOG_SELLER, OWNER_ID
from database import dB
from command import payment_command as pay
from command import pay_peller as extra

LOCK = asyncio.Lock()
TESTIMONI_ID = LOG_SELLER
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


def active(book, uid):
    return next((o for o in book["orders"].values() if o["buyer"] == uid and o["state"] in ("awaiting_photo", "proof", "logged")), None)


async def inventory(kind, key):
    return await extra.nf_list() if kind == "nf" else await pay.get_nokos_list(key)


async def create(uid, kind, key):
    book = await load()
    if active(book, uid) or uid in pay.transactions:
        raise ValueError("Masih ada pesanan aktif. Kirim bukti untuk pesanan itu atau batalkan dahulu.")
    if kind == "nk":
        if key not in pay.NOKOS_IDS:
            raise ValueError("ID nokos tidak valid.")
        name, amount = f"Nokos {pay.nokos_label(key).strip()}", pay.get_nokos_price(key)
    elif kind in ("nf", "tp", "st"):
        name, amount = extra.item_info(kind, key)
    elif kind == "gc":
        name, amount = "Suntik GC/CH", None
    else:
        raise ValueError("Produk tidak valid.")
    stock = None
    if kind in ("nk", "nf"):
        used = {(phone(o.get("stock")) if kind == "nk" else o.get("stock")) for o in book["orders"].values() if o["kind"] == kind and o["state"] != "cancelled"}
        available = await inventory(kind, key)
        stock = next((value for value in available if (phone(value) if kind == "nk" else value) not in used and (kind != "nk" or book["sessions"].get(phone(value), {}).get("ready"))), None)
        if not stock:
            raise ValueError("Stok siap kirim habis. Nokos wajib sudah didaftarkan session-nya oleh owner.")
    oid = token_hex(6)
    order = {"id": oid, "buyer": uid, "kind": kind, "key": key, "name": name, "amount": amount, "stock": stock,
             "created": time.time(), "state": "awaiting_photo", "testimoni": TESTIMONI_ID, "invoice_sent": False}
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
        amount = "Sesuai kesepakatan dengan owner" if order["amount"] is None else f"Rp{order['amount']:,}".replace(",", ".")
        caption = (f"Pesanan #{order['id']}\nItem: {order['name']}\nTotal: {amount}\n\n"
                   "Bayar ke QRIS ini, lalu kirim FOTO bukti ke bot. Pesanan berlaku 30 menit.\n"
                   "Foto yang diterima log memicu pengiriman tanpa verifikasi dana otomatis.")
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "qris.png")
            await pay.make_qr_image(CODEQR, path)
            await client.send_photo(order["buyer"], path, caption=caption, reply_markup=ikb([
                [("Batalkan", "batal_payment", ButtonStyle.DANGER)],
            ]))
    except ValueError as error:
        await query.answer(str(error)[:190], show_alert=True)
    except Exception:
        await client.send_message(query.from_user.id, "Pesanan belum selesai dibuka. Gunakan /pesananku untuk melihat status atau mengirim bukti.")


async def accept_photo(message):
    async with LOCK:
        book = await load()
        order = active(book, message.from_user.id)
        if not order:
            return False
        if order["state"] != "awaiting_photo":
            await message.reply("Bukti sebelumnya sedang diproses. Tidak perlu kirim ulang.")
            return True
        if time.time() - order["created"] >= 1800:
            await cancel(order)
            await message.reply("Pesanan kedaluwarsa. Buat pesanan baru dahulu.")
            return True
        unique = message.photo.file_unique_id
        if any(o.get("proof_unique") == unique for o in book["orders"].values()):
            await message.reply("Foto ini sudah pernah dipakai sebagai bukti pesanan. Kirim bukti yang sesuai pesanan ini.")
            return True
        order.update(state="proof", proof=message.photo.file_id, proof_unique=unique, proof_at=time.time())
        await save()
    await message.reply("Bukti diterima bot dan sedang diteruskan ke log. Tunggu pengiriman pesanan.")
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
        await send(LOG_SELLER, f"Bukti foto diterima, BELUM verifikasi dana.\nPesanan #{oid}\nBuyer: {uid}\nItem: {order['name']}",
                   f"{oid}:proof", photo_id=order["proof"], markup=done_button(oid))
        order["state"] = "logged"
        await save()
    if order["state"] != "logged":
        return
    kind = order["kind"]
    if kind == "nk":
        await pay.sell_nokos(order["key"], order["stock"])
        text = f"Transaksi berhasil.\nItem: {order['name']}\nNomor: {order['stock']}\n\nSilakan login. OTP baru akan dikirim bot saat diterima akun stok; pemantauan berlaku 10 menit."
    elif kind == "nf":
        await extra.nf_sell(order["stock"])
        text = f"Transaksi berhasil.\nItem: {order['name']}\nAkun: {order['stock']}\n\nJangan mengubah email/password akun."
    else:
        text = f"Transaksi berhasil, item yang dibeli {order['name']}. Tunggu owner membalas."
    if not order.get("delivery_at"):
        order["delivery_at"] = time.time()
        await save()
    await send(uid, text, f"{oid}:delivery", markup=done_button(oid))
    order.update(state="delivered" if kind in ("nk", "nf") else "waiting_owner", invoice_due=order["delivery_at"] + 1800)
    await save()


def invoice(order, now=None):
    timestamp = datetime.fromtimestamp(order.get("delivery_at", order["created"]), pay.waktu_jkt).strftime("%d-%m-%Y %H:%M WIB")
    amount = "Sesuai kesepakatan owner" if order["amount"] is None else f"Rp{order['amount']:,}".replace(",", ".")
    status = "Data produk sudah dikirim" if order["state"] == "delivered" else "Menunggu diproses owner"
    completion = order.get("completed_by")
    if completion == "owner":
        status = "Owner menyatakan transaksi selesai"
    confirmation = "Buyer menekan Transaksi Selesai" if completion == "buyer" else "Owner menekan Transaksi Selesai" if completion else "Belum dikonfirmasi buyer"
    publication = "Tombol Transaksi Selesai" if completion else "Otomatis setelah 30 menit"
    masked = str(order["buyer"])[:3] + "***"
    return (f"🧾 BUKTI PEMBELIAN\n\nID Pesanan : VIP-{order['id'].upper()}\nProduk : {order['name']}\n"
            f"Pembeli : Buyer #{masked}\nTotal : {amount}\nTanggal : {timestamp}\n\n"
            f"📦 Status : {status}\n✅ Konfirmasi : {confirmation}\n📌 Publikasi : {publication}\n"
            "🧾 Dasar pesanan : Foto bukti diterima, bukan verifikasi dana otomatis.\n\nTerima kasih sudah berbelanja!")


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
    oid = query.data.split(":", 1)[1]
    async with LOCK:
        order = (await load())["orders"].get(oid)
        if not order or query.from_user.id not in (order["buyer"], OWNER_ID):
            return await query.answer("Pesanan ini bukan milikmu.", show_alert=True)
        if order["state"] not in ("delivered", "waiting_owner"):
            return await query.answer("Pesanan belum berhasil dikirim/dicatat. Tunggu prosesnya.", show_alert=True)
        if order.get("invoice_sent"):
            return await query.answer("Invoice sudah dikirim sebelumnya.", show_alert=True)
        order.setdefault("completed_by", "owner" if query.from_user.id == OWNER_ID else "buyer")
        order["invoice_due"] = time.time()
        await save()
    await query.answer("Transaksi dicatat selesai. Invoice akan dikirim ke testimoni.")


async def bind(message):
    if message.from_user.id != OWNER_ID or message.chat.id != OWNER_ID:
        return
    parts = message.text.split()
    if len(parts) != 3:
        return await message.reply("Format: /bindnokos +628xxx USERBOT_ID. Hanya bind akun stok milik sendiri yang sudah login lewat alur pembuatan userbot repo ini.")
    number, uid = phone(parts[1]), int(parts[2])
    from clients import alice
    app = next((a for a in alice._ubot if a.me.id == uid and phone(a.me.phone_number) == number), None)
    if not app:
        return await message.reply("Userbot stok belum aktif atau nomornya tidak cocok. Login akun stok milikmu dahulu lewat alur pembuatan userbot.")
    async with LOCK:
        book = await load()
        stock = [n for key in pay.NOKOS_IDS for n in await pay.get_nokos_list(key)]
        if number not in {phone(n) for n in stock}:
            return await message.reply("Nomor harus sudah terdaftar di stok nokos.")
        if any(o["kind"] == "nk" and phone(o.get("stock") or "") == number and o["state"] != "cancelled" for o in book["orders"].values()):
            return await message.reply("Nomor sudah dipesan atau terjual; tidak dapat diikat ulang.")
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
    await message.reply("Session stok disimpan privat dan dipisahkan dari userbot umum. OTP hanya diteruskan untuk pesanan nomor tersebut.")


async def otp(order):
    number = phone(order["stock"])
    if order.get("otp_sent") or time.time() > order["delivery_at"] + 600:
        app = _APPS.pop(number, None)
        if app:
            await app.disconnect()
        if number in _BOOK["sessions"]:
            del _BOOK["sessions"][number]
            await save()
        return
    binding = _BOOK["sessions"].get(number)
    if not binding:
        return
    app = _APPS.get(number)
    if app is None:
        app = Client(f"nokos-{number}", api_id=API_ID, api_hash=API_HASH, session_string=binding["session"], in_memory=True)
        await app.connect()
        me = await app.get_me()
        if phone(me.phone_number) != number:
            await app.disconnect()
            raise ValueError("Session stok tidak cocok")
        _APPS[number] = app
    if not order.get("otp_code"):
        messages = [m async for m in app.get_chat_history(777000, limit=10)]
        for message in reversed(messages):
            text = message.text or ""
            match = re.search(r"(?i)(?:login code|kode login|kode masuk|telegram code)\D{0,30}(\d{5})\b", text)
            if message.id > binding["baseline"] and message.date.timestamp() >= order["delivery_at"] and match:
                order.update(otp_code=match.group(1), otp_message_id=message.id)
                await save()
                break
    if order.get("otp_code"):
        await send(order["buyer"], f"OTP untuk pesanan #{order['id']}: {order['otp_code']}\nJangan bagikan kode ini ke orang lain.", f"{order['id']}:otp")
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
                        if not order.get("error_notified"):
                            try:
                                await bot.send_message(OWNER_ID, f"Pesanan #{order['id']} perlu dicek. Tahap: {order['state']}. Jenis error: {type(error).__name__}. Tidak ada kredensial yang ditampilkan.")
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
