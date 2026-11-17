import asyncio
import hashlib
import os
import re
import time
from html import escape

import httpx
from pyrogram import StopPropagation, filters
from pyrogram.enums import ButtonStyle
from pyrogram.helpers import ikb

from clients import bot
from config import LOG_SELLER
from database import dB
from command.payment_command import (
    QRIS_EXPIRE_MINUTES, CasakuError, PAID_STATUSES,
    check_status, generate_qris, make_qr_image, transactions,
    _delete_qr_message, _remove_file,
)

API_URL = "https://api.gramix.io/api/v1"
API_KEY = os.getenv("GRAMIX_API_KEY", "7JOMoCTB4kwAmF6eTxFEVlOhu4zXBHp1RwVhcpWOW0A").strip()
CURRENCY = os.getenv("GRAMIX_CURRENCY", "usdt").strip().lower()
ORDER_VAR = "GRAMIX_STARS_ORDER"
P, S, D = ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER
TASKS, LOCKS = {}, {}
TERMINAL = {"completed", "failed", "canceled", "expired"}
USERNAME = re.compile(r"[a-z][a-z0-9_]{4,31}")


class GramixError(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Gramix HTTP {status}")


def rupiah(value):
    return "Rp" + f"{int(value):,}".replace(",", ".")


def lock_for(uid):
    return LOCKS.setdefault(uid, asyncio.Lock())


def price_for(quantity):
    return quantity * (286 if quantity <= 500 else 283)


async def save(uid, order):
    await dB.set_var(uid, ORDER_VAR, order)


async def load(uid):
    order = await dB.get_var(uid, ORDER_VAR)
    return order if isinstance(order, dict) else {}


async def tell(client, uid, text):
    try:
        await client.send_message(uid, text)
    except Exception:
        pass


async def admin(client, uid, order, reason):
    await tell(
        client, LOG_SELLER,
        "<b>Order Stars perlu diperiksa</b>\n"
        f"User: <code>{uid}</code>\n"
        f"Tujuan: @{escape(order['recipient'])}\n"
        f"Jumlah: {order['quantity']:,}\n"
        f"Casaku: <code>{escape(order.get('payment_id', '-'))}</code>\n"
        f"Gramix: <code>{escape(order.get('order_id', '-'))}</code>\n"
        f"Keterangan: {escape(reason)}",
    )


async def api(method, path, payload=None, key=None):
    if not API_KEY:
        raise GramixError(401)
    headers = {"x-api-key": API_KEY, "Accept": "application/json"}
    if key:
        headers["idempotency-key"] = key
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as http:
        response = await http.request(
            method, API_URL + path, headers=headers, json=payload,
        )
    if not response.is_success:
        raise GramixError(response.status_code)
    body = response.json()
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise ValueError("Respons Gramix tidak sesuai dokumentasi")
    return body["data"]


def start_monitor(client, uid):
    task = TASKS.get(uid)
    if task and not task.done():
        return
    task = asyncio.create_task(monitor(client, uid))
    TASKS[uid] = task

    def finished(done):
        if TASKS.get(uid) is done:
            TASKS.pop(uid, None)
        if not done.cancelled():
            done.exception()

    task.add_done_callback(finished)


async def monitor(client, uid):
    notified = False
    for _ in range(180):
        try:
            async with lock_for(uid):
                order = await load(uid)
                state = order.get("state")
                if not order or state in TERMINAL:
                    return

                if state in {"creating", "review"}:
                    return

                if state == "awaiting_payment":
                    result = await check_status(order["payment_id"])
                    payment = str(result.get("status", "")).strip().lower()
                    if payment in PAID_STATUSES:
                        order["state"] = "paid"
                        await save(uid, order)
                        transactions.pop(uid, None)
                        await _delete_qr_message(
                            client, uid, order.get("message_id", 0),
                        )
                        await tell(
                            client, uid,
                            "Pembayaran terverifikasi. Pengiriman Stars diproses.",
                        )
                    elif payment in {"expired", "cancel", "cancelled", "canceled"}:
                        order["state"] = "expired"
                        await save(uid, order)
                        transactions.pop(uid, None)
                        await _delete_qr_message(
                            client, uid, order.get("message_id", 0),
                        )
                        await tell(client, uid, "Tagihan kedaluwarsa atau dibatalkan.")
                        return
                    elif time.time() > order["check_until"]:
                        await tell(
                            client, uid,
                            "Status pembayaran belum pasti. Jangan bayar ulang. "
                            "Gunakan /statusstars atau hubungi admin.",
                        )
                        return

                if order["state"] in {"paid", "submitting"}:
                    order["state"] = "submitting"
                    await save(uid, order)
                    result = await api(
                        "POST", "/purchase/stars",
                        {
                            "recipientName": order["recipient"],
                            "paymentCurrency": order["currency"],
                            "stars": order["quantity"],
                        },
                        order["request_key"],
                    )
                    order["order_id"] = result["orderId"]
                    order["state"] = "processing"
                    await save(uid, order)

                if order["state"] == "processing":
                    result = await api("GET", f"/orders/{order['order_id']}")
                    status = result.get("status")
                    if status in {"completed", "failed", "canceled"}:
                        order["state"] = status
                        order["provider_result"] = result
                        await save(uid, order)
                        if status == "completed":
                            text = (
                                "<b>Stars berhasil dikirim</b>\n"
                                f"Tujuan: @{order['recipient']}\n"
                                f"Jumlah: {order['quantity']:,} Stars\n"
                                f"Harga: {rupiah(order['price'])}\n"
                                f"Order: <code>{escape(order['order_id'])}</code>"
                            )
                            await tell(client, uid, text)
                            await tell(client, LOG_SELLER, f"Pembeli: {uid}\n{text}")
                        else:
                            await tell(
                                client, uid,
                                "Pembayaran diterima, tetapi pengiriman tidak berhasil. "
                                "Admin perlu memeriksa pesanan/refund. Jangan bayar ulang.",
                            )
                            await admin(client, uid, order, f"Status Gramix: {status}")
                        return
            notified = False

        except GramixError as error:
            async with lock_for(uid):
                order = await load(uid)
                if error.status in {400, 401, 403, 404, 405, 422}:
                    order["resume_state"] = order.get("state", "paid")
                    order["state"] = "review"
                    await save(uid, order)
                    await tell(
                        client, uid,
                        "Pengiriman membutuhkan pemeriksaan admin. "
                        "Pembayaranmu tetap tercatat; jangan bayar ulang.",
                    )
                    await admin(client, uid, order, str(error))
                    return
            if not notified:
                await admin(client, uid, order, str(error))
                notified = True

        except (httpx.HTTPError, ValueError, KeyError, CasakuError) as error:
            if not notified:
                order = await load(uid)
                if order:
                    await admin(
                        client, uid, order,
                        f"Gangguan sementara: {type(error).__name__}. "
                        "Status belum dianggap gagal.",
                    )
                notified = True

        except asyncio.CancelledError:
            raise

        except Exception:
            await tell(
                client, uid,
                "Pemantauan terhenti. Gunakan /statusstars untuk melanjutkan. "
                "Jangan membuat pembayaran ulang.",
            )
            return

        await asyncio.sleep(5)

    await tell(
        client, uid,
        "Pesanan belum selesai dipantau. Gunakan /statusstars untuk "
        "memeriksa dan melanjutkan pesanan yang sama.",
    )


async def checkout(client, query):
    uid = query.from_user.id
    async with lock_for(uid):
        current = await load(uid)
        if uid in transactions or (
            current and current.get("state") not in TERMINAL
        ):
            await query.answer("Masih ada pesanan. Gunakan /statusstars.", show_alert=True)
            return
        if not API_KEY or CURRENCY not in {"usdt", "gram"}:
            await query.answer("Konfigurasi Gramix belum siap.", show_alert=True)
            return
        await query.answer()
        await save(uid, {"state": "creating"})

    qr_path = None
    invoice_created = False
    payment_id = None
    order = None
    try:
        recipient = await client.ask(
            uid, "Kirim username penerima, contoh: @username.\nKetik /batal untuk keluar.",
            filters=filters.text & filters.private & filters.user(uid), timeout=120,
        )
        username = (recipient.text or "").strip().lstrip("@").lower()
        if username == "/batal":
            raise ValueError("Pembelian dibatalkan.")
        if not USERNAME.fullmatch(username):
            raise ValueError("Username tidak valid. Buka menu Stars untuk mencoba lagi.")

        answer = await client.ask(
            uid,
            "Masukkan jumlah Stars: 50–1.000.000.\n"
            "50–500: Rp286/Stars; 501+: Rp283/Stars.\nKetik /batal untuk keluar.",
            filters=filters.text & filters.private & filters.user(uid), timeout=120,
        )
        raw = (answer.text or "").strip()
        if raw == "/batal":
            raise ValueError("Pembelian dibatalkan.")
        if not raw.isascii() or not raw.isdecimal():
            raise ValueError("Jumlah harus angka bulat tanpa titik atau koma.")
        quantity = int(raw)
        if not 50 <= quantity <= 1_000_000:
            raise ValueError("Jumlah harus antara 50 dan 1.000.000 Stars.")

        await api("GET", "/wallets/balance")
        price = price_for(quantity)
        trx = await generate_qris(price, QRIS_EXPIRE_MINUTES)
        payment_id = str(trx["transactionId"])
        invoice_created = True
        minutes = int(trx.get("expiredInMinutes", QRIS_EXPIRE_MINUTES))
        order = {
            "state": "awaiting_payment", "recipient": username,
            "quantity": quantity, "price": price, "currency": CURRENCY,
            "payment_id": payment_id,
            "request_key": "stars_" + hashlib.sha256(payment_id.encode()).hexdigest()[:48],
            "check_until": time.time() + (minutes + 10) * 60,
        }
        await save(uid, order)
        qr_path = f"stars_{uid}_{order['request_key'][-16:]}.png"
        await make_qr_image(trx["qr_string"], qr_path)
        sent = await client.send_photo(
            uid, qr_path,
            caption=(
                "<b>Pembayaran Telegram Stars</b>\n"
                f"Tujuan: @{username}\nJumlah: {quantity:,} Stars\n"
                f"Harga: {rupiah(price)}\n"
                f"Total bayar: {rupiah(trx['totalAmount'])}\n"
                f"Masa berlaku: {minutes} menit\n\n"
                "Periksa tujuan sebelum membayar. Bayar sesuai total QRIS.\n"
                "Stars diproses setelah pembayaran terverifikasi.\n"
                "Cek pesanan: /statusstars"
            ),
        )
        order["message_id"] = sent.id
        await save(uid, order)
        start_monitor(client, uid)

    except ValueError as error:
        if not invoice_created:
            await save(uid, {"state": "canceled"})
        await tell(
            client, uid,
            "Respons layanan perlu diperiksa. Gunakan /statusstars."
            if invoice_created else escape(str(error)),
        )

    except Exception as error:
        if not invoice_created:
            await save(uid, {"state": "canceled"})
        await tell(
            client, uid,
            "Tidak bisa menampilkan tagihan. Gunakan /statusstars; jangan bayar "
            "tagihan lain jika sudah menerima QRIS."
            if invoice_created else
            "Pesanan belum dapat dimulai. Coba lagi atau hubungi admin.",
        )
        await tell(
            client, LOG_SELLER,
            f"Checkout Stars user {uid}: {type(error).__name__}. "
            f"Casaku: {escape(payment_id or '-')}",
        )

    finally:
        _remove_file(qr_path)
        if invoice_created and order:
            start_monitor(client, uid)


@bot.on_callback_query(
    filters.regex(r"^(?:planusers stars|p2star(?: .*)?|p2buy st .*)$"),
    group=-50,
)
async def stars_menu(client, query):
    try:
        await checkout(client, query)
    finally:
        raise StopPropagation


@bot.on_message(filters.private & filters.command("statusstars"), group=-50)
async def stars_status(client, message):
    uid = message.from_user.id
    order = await load(uid)
    labels = {
        "creating": "Sedang mengisi pesanan",
        "awaiting_payment": "Menunggu konfirmasi pembayaran",
        "paid": "Pembayaran diterima",
        "submitting": "Mengonfirmasi permintaan ke Gramix",
        "processing": "Pengiriman diproses",
        "review": "Perlu pemeriksaan admin",
        "completed": "Stars berhasil dikirim",
        "failed": "Pengiriman gagal; hubungi admin",
        "canceled": "Dibatalkan",
        "expired": "Tagihan kedaluwarsa",
    }
    if not order:
        await message.reply("Belum ada pesanan Stars.")
    else:
        state = order.get("state", "")
        text = f"Status: {labels.get(state, state)}"
        if order.get("recipient"):
            text += (
                f"\nTujuan: @{order['recipient']}"
                f"\nJumlah: {order['quantity']:,} Stars"
                f"\nHarga: {rupiah(order['price'])}"
            )
        if order.get("payment_id"):
            text += f"\nCasaku: <code>{escape(order['payment_id'])}</code>"
        if order.get("order_id"):
            text += f"\nGramix: <code>{escape(order['order_id'])}</code>"
        await message.reply(text)
        if state not in TERMINAL and state not in {"creating", "review"}:
            start_monitor(client, uid)
    raise StopPropagation