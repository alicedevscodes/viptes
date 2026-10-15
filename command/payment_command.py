######################################################
# UPDATES PAYMENT GATEWAY CASAKU.ID

# ©CREDITS: @ALICEDEVSCODES as DEVA | @MELIN -> TEMEN GUA 
# DIKATA COPAS LU BABJ ANJING ASYU
# NGAKU NGAKH BOOL NYA PANAS 7 TURUNAN 

######################################################

import asyncio
import os
import time
import traceback
from datetime import datetime, timedelta

import httpx
import qrcode
from dateutil.relativedelta import relativedelta
from pyrogram import filters, enums
from pyrogram.enums import ButtonStyle
from pyrogram.helpers import (send_rich,
    paragraph,
    heading,
    divider,
    footer,
    table,
    cell,
    ikb
)
from pyrogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                            KeyboardButton, ReplyKeyboardMarkup,
                            ReplyKeyboardRemove)
from pytz import timezone

from clients import bot
from config import (AKSES_DEPLOY, CASAKU_BASE_URL, CASAKU_LICENSE_KEY,
                    CASAKU_PACKAGE_IDS, CASAKU_QRIS_ID, LOG_SELLER, OWNER_ID,
                    VIP_CHANNEL_BASIC, VIP_CHANNEL_PRO)
from database import dB
from helpers import ButtonUtils, Emoji, Message, emo
from logs import logger

transactions = {}
waktu_jkt = timezone("Asia/Jakarta")

PRICES = {
    "basic": 5,
    "pro": 5,
}
QRIS_EXPIRE_MINUTES = 5
POLL_INTERVAL = 4
PAID_STATUSES = ("paid", "success", "settlement", "completed", "lunas")
INVITE_EXPIRE_MINUTES = 10  # masa berlaku link channel, setelah itu di-revoke

# plan yang dibeli -> ID channel private yang sesuai
VIP_CHANNELS = {
    "basic": VIP_CHANNEL_BASIC,
    "pro": VIP_CHANNEL_PRO,
}


PRODUCT_BY_PLAN = {
    "basic": "vip",
    "pro": "vip",
    "is_pro": "vip",
}


NOKOS_OWNER = OWNER_ID        # pemilik vars stok nokos
NOKOS_IDS = ["nokos_id1", "nokos_id2", "nokos_id5", "nokos_id6", "nokos_id7", "nokos_id8", "nokos_id9"]  # id yang dijual
NOKOS_DEFAULT_PRICE = 5          
NOKOS_PRICES = { 
  "nokos_id1": 1,
  "nokos_id2": 2,
  "nokos_id5": 5,
  "nokos_id6": 6,
  "nokos_id7": 7,
  "nokos_id8": 8,
  "nokos_id9": 9,
}

nokos_lock = asyncio.Lock()
reserved_nokos = {}  # nomor -> user_id (sedang dibayar, supaya tidak dobel jual)

_http_client = None


class CasakuError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        super().__init__(f"[{status}] {message}")

    @property
    def user_message(self):
        if self.status == 403:
            return "Sistem pembayaran sedang offline. Silakan coba lagi beberapa menit lagi."
        if self.status == 429:
            return "Terlalu banyak permintaan. Tunggu sebentar lalu coba lagi."
        if self.status in (401, 0, 408):
            return "Sistem pembayaran sedang bermasalah. Silakan hubungi admin."
        return "Terjadi kesalahan pada pembayaran. Silakan coba lagi."

    @property
    def admin_message(self):
        if self.status == 401:
            return "License Key Casaku tidak valid / belum diisi (401)."
        if self.status == 403:
            return "Listener Casaku OFFLINE (403). Casaku Belum Premium."
        if self.status == 429:
            return "Rate limit Casaku tercapai (429)."
        return str(self)


def _get_http():
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=CASAKU_BASE_URL.rstrip("/"),
            headers={
                "x-license-key": CASAKU_LICENSE_KEY,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(15.0),
        )
    return _http_client


async def _request(method, path, **kwargs):
    if not CASAKU_LICENSE_KEY:
        raise CasakuError(401, "CASAKU_LICENSE_KEY belum diisi")
    try:
        resp = await _get_http().request(method, path, **kwargs)
    except httpx.TimeoutException:
        raise CasakuError(408, "Timeout menghubungi Casaku")
    except httpx.HTTPError as e:
        raise CasakuError(0, f"Koneksi ke Casaku gagal: {e}")

    try:
        body = resp.json()
    except ValueError:
        body = {}

    if resp.status_code != 200 or body.get("status", 200) != 200:
        code = resp.status_code if resp.status_code != 200 else body.get("status", 500)
        raise CasakuError(code, body.get("message") or resp.text[:200])
    return body.get("data", body)


async def generate_qris(amount, expired_minutes=QRIS_EXPIRE_MINUTES):
    payload = {
        "id": CASAKU_QRIS_ID,
        "amount": int(amount),
        "useUniqueCode": True,
        "packageIds": [p.strip() for p in str(CASAKU_PACKAGE_IDS).split(",") if p.strip()],
        "expiredInMinutes": expired_minutes,
    }
    result = await _request("POST", "/api/generate/qris", json=payload)
    logger.info(f"CASAKU GENERATE: {result}")
    return result


async def check_status(transaction_id):
    return await _request(
        "POST", "/api/generate/check-status", json={"transactionId": transaction_id}
    )


async def cancel_transaction(transaction_id):
    return await _request(
        "POST", "/api/generate/cancel-status", json={"transactionId": transaction_id}
    )


async def make_qr_image(qr_string, path):
    await asyncio.to_thread(lambda: qrcode.make(qr_string).save(path))
    return path


async def wait_for_payment(transaction_id, expired_minutes, is_active):
    deadline = time.monotonic() + (expired_minutes + 1) * 60
    errors = 0
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_INTERVAL)
        if not is_active():
            return "cancelled"
        try:
            data = await check_status(transaction_id)
            errors = 0
        except CasakuError as e:
            errors += 1
            if e.status == 401 or errors >= 5:
                raise
            if e.status == 429:
                await asyncio.sleep(10)
            continue

        raw_status = str(data.get("status", "")).strip().lower()
        logger.info(f"CASAKU CHECK {transaction_id[:8]}: {data}")
        if raw_status in PAID_STATUSES:
            return "paid"
        if raw_status in ("cancel", "cancelled", "canceled"):
            return "cancel"
        if raw_status == "expired":
            return "expired"
    return "expired"


def normalize_plan(plan):
    return "basic" if str(plan).lower() == "basic" else "pro"


def plan_label(plan):
    return "Basic" if normalize_plan(plan) == "basic" else "Pro"


def get_price(plan, month):
    return PRICES[normalize_plan(plan)] * month


# [BARU] tentukan jenis produk dari plan ("vip" / "ubot")
def get_product(plan):
    return PRODUCT_BY_PLAN.get(str(plan).lower(), "vip")


async def notify_admin(client, text):
    try:
        await client.send_message(LOG_SELLER, f"<b>⚠️ Casaku:</b> {text}")
    except Exception:
        pass


async def add_transaction(user_id, month, plan):
    await dB.set_var(user_id, "plan", plan)
    expired = await dB.get_expired_date(user_id)
    if not expired:
        now = datetime.now(waktu_jkt)
        expired = now + relativedelta(months=month)
        await dB.set_expired_date(user_id, expired)


def _remove_file(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


async def _delete_qr_message(client, chat_id, message_id):
    try:
        await client.delete_messages(chat_id=chat_id, message_ids=message_id)
    except Exception:
        pass


def nokos_label(nokos_id):
    return " " + str(nokos_id).replace("nokos_id", "ID ")


def get_nokos_price(nokos_id):
    return int(NOKOS_PRICES.get(nokos_id, NOKOS_DEFAULT_PRICE))


async def get_nokos_list(nokos_id):
    """Baca semua nomor di var nokos_idX -> list."""
    raw = await dB.get_var(NOKOS_OWNER, nokos_id)
    raw = str(raw or "").replace("\n", ",")
    return [n.strip() for n in raw.split(",") if n.strip()]


async def save_nokos_list(nokos_id, numbers):
    await dB.set_var(NOKOS_OWNER, nokos_id, ", ".join(numbers))


async def get_available_nokos(nokos_id):
    """Nomor yang masih bisa dijual (tidak sedang dipesan orang lain)."""
    numbers = await get_nokos_list(nokos_id)
    return [n for n in numbers if n not in reserved_nokos]


async def reserve_nokos(nokos_id, user_id):
    """Booking 1 nomor selama pembayaran berlangsung (belum dihapus dari vars)."""
    async with nokos_lock:
        for number in await get_nokos_list(nokos_id):
            if number not in reserved_nokos:
                reserved_nokos[number] = user_id
                return number
    return None


def release_nokos(number):
    """Batalkan booking (transaksi batal/expired/error)."""
    if number:
        reserved_nokos.pop(number, None)


async def sell_nokos(nokos_id, number):
    """Nomor terjual -> hapus dari vars."""
    async with nokos_lock:
        numbers = await get_nokos_list(nokos_id)
        if number in numbers:
            numbers.remove(number)
            await save_nokos_list(nokos_id, numbers)
        reserved_nokos.pop(number, None)


async def take_nokos(nokos_id):
    """Ambil 1 nomor langsung dari vars (dipakai tombol manual admin)."""
    async with nokos_lock:
        numbers = await get_nokos_list(nokos_id)
        for number in numbers:
            if number not in reserved_nokos:
                numbers.remove(number)
                await save_nokos_list(nokos_id, numbers)
                return number
    return None


async def restock_nokos(nokos_id, number):
    """Kembalikan nomor ke vars (kalau gagal kirim ke pembeli)."""
    async with nokos_lock:
        numbers = await get_nokos_list(nokos_id)
        if number not in numbers:
            numbers.append(number)
            await save_nokos_list(nokos_id, numbers)

# Tambah Stok Nokos
async def tambah_nokos_cmd(client, message):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return await message.reply("<b>❌ Perintah ini hanya untuk Owner.</b>")

    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply(
            "<b>Format salah.</b>Contoh: <code>/nokos1 0811111 0811112</code>"
        )

    nokos_id = "nokos_id" + parts[0].replace("/nokos", "")
    if nokos_id not in NOKOS_IDS:
        return await message.reply(
            f"<b>❌ ID nokos tidak terdaftar:</b> <code>{nokos_id}</code>"
        )

    new_numbers = [n.strip() for n in parts[1:] if n.strip()]
    current = await get_nokos_list(nokos_id)

    added, duplicate = [], []
    for number in new_numbers:
        if number in current:
            duplicate.append(number)
        else:
            current.append(number)
            added.append(number)

    if added:
        await save_nokos_list(nokos_id, current)

    text = f"<b>✅ {nokos_label(nokos_id)} berhasil disimpan.</b>"
    text += f"<blockquote>📦 Stok sekarang: <code>{len(current)}</code></blockquote>"
    if added:
        text += f"<b>➕ Ditambahkan:</b> <code>{', '.join(added)}</code>\n"
    if duplicate:
        text += f"<b>⚠️ Sudah ada:</b> <code>{', '.join(duplicate)}</code>"

    await message.reply(text)

async def hapus_nokos_cmd(client, message):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return await message.reply("<b>❌ Perintah ini hanya untuk Owner.</b>")

    targets = [n.strip() for n in message.text.split()[1:] if n.strip()]
    if not targets:
        return await message.reply(
            "<b>Format salah.</b>\nContoh: <code>/del 0811111</code>\n"
            "Bisa beberapa: <code>/del 0811111 0811112</code>"
        )
    lines, changed = [], set()
    async with nokos_lock:
        data = {nid: await get_nokos_list(nid) for nid in NOKOS_IDS}
        for number in targets:
            if number in reserved_nokos:
                lines.append(f"⏳ <code>{number}</code> sedang dibayar pembeli, coba lagi nanti.")
                continue
            found = [nid for nid, nums in data.items() if number in nums]
            if not found:
                lines.append(f"⚠️ <code>{number}</code> tidak ditemukan di database manapun.")
                continue
            for nid in found:
                data[nid].remove(number)
                changed.add(nid)
            ids = ", ".join(nid.replace("nokos_", "") for nid in found)
            lines.append(f"<blockquote><b>✅ Sukses menghapus <code>{number}</code> dari database {ids}</b></blockquote>")
        for nid in changed:
            await save_nokos_list(nid, data[nid])

    await message.reply("" + "\n".join(lines))

async def stok_nokos_cmd(client, message):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return await message.reply("<b>❌ Perintah ini hanya untuk Owner.</b>")

    lines = []
    total = 0
    for nokos_id in NOKOS_IDS:
        numbers = await get_nokos_list(nokos_id)
        total += len(numbers)
        lines.append(
            f"<b>{nokos_label(nokos_id)}</b>\n\n"
            f"<b>📦 Stok:</b> <code>{len(numbers)}</code>\n"
            f"<b>📱 Nomor:</b> <code>{', '.join(numbers) if numbers else 'Kosong'}</code>\n"
        )

    await message.reply(
        "<b>📊 Stok Nokos</b>\n"
        + "".join(lines)
        + f"\n<b>Total semua stok:</b> <code>{total}</code>"
    )


async def kirim_nomor_nokos(client, user_id, nokos_id, number):
    await client.send_message(
        user_id,
        f"""<b>✅ Pembayaran Berhasil</b>

<blockquote><b>Produk: {nokos_label(nokos_id)}
📱 Nomor: <code>{number}</code></b></blockquote>

<blockquote><b>Simpan nomor di atas. Jika butuh bantuan, hubungi admin.</b></blockquote>""",
    )


# ------------------------------------------------------------------
# LINK INVITE CHANNEL PRIVATE (SEKALI KLIK) + REVOKE
# ------------------------------------------------------------------
async def _revoke_link_later(client, channel_id, invite_link, delay):
    """Tunggu `delay` detik lalu cabut link supaya tidak bisa dipakai lagi."""
    try:
        await asyncio.sleep(delay)
        await client.revoke_chat_invite_link(channel_id, invite_link)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        # link yang sudah terpakai / kedaluwarsa kadang tidak bisa di-revoke lagi
        logger.warning(f"Revoke invite link gagal/sudah tidak aktif: {e}")


async def kirim_link_vip(client, user_id, plan):
    """
    Buat link invite sekali pakai (member_limit=1) ke channel private
    SESUAI PLAN yang dibeli, kirim ke pembeli, lalu revoke otomatis.
    """
    plan = normalize_plan(plan)
    channel_id = VIP_CHANNELS.get(plan)
    if not channel_id:
        raise ValueError(f"Channel untuk plan '{plan}' belum diatur di config")

    expire_at = datetime.now(waktu_jkt) + timedelta(minutes=INVITE_EXPIRE_MINUTES)
    link = await client.create_chat_invite_link(
        chat_id=channel_id,
        name=f"VIP {plan} {user_id}",
        expire_date=expire_at,
        member_limit=1,
    )
    invite_link = link.invite_link

    await client.send_message(
        user_id,
        f"""<b>✅ Pembayaran Berhasil</b>

<blockquote><b>Plan: {plan_label(plan)}
Klik tombol di bawah untuk masuk ke channel private.
⚠️ Link hanya bisa dipakai <u>1 kali</u> dan berlaku {INVITE_EXPIRE_MINUTES} menit.</b></blockquote>""",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 Masuk Channel Private", url=invite_link)]]
        ),
    )

    # cabut link setelah masa berlaku habis
    asyncio.create_task(
        _revoke_link_later(client, channel_id, invite_link, INVITE_EXPIRE_MINUTES * 60 + 5)
    )
    return invite_link

def menu_blocks():
    return (
        heading(
            [
                emo(5373052667671093676, "💎"),
                " Seblak Ultra Pedasss",
            ],
            3,
        ),
        divider(),
        table(
            [
                [
                    cell([emo(5258397811329739167, "💎"), " SEBLAK DINGIN"], is_header=True, align="center"),
                    cell([emo(5458908492687497206, "💎"), " ULTRA PEDAS MENCRET"], is_header=True, align="center"),
                ],
                [
                    cell("Rasa"),
                    cell([emo(5372824841130879657, "✅"), " Ga enak"], align="center"),
                ],
                [
                    cell("Gratis"),
                    cell([emo(5258190433128834075, "✅"), " Tidak"], align="center"),
                ],
                [
                    cell("Efek Mencret"),
                    cell([emo(5456140674028019486, "✅"), " Iya"], align="center"),
                ],
                [
                    cell("Harga per bulan"),
                    cell([emo(5269720586367542578, "💰"), " Rp10.000.000.000"], align="center"),
                ],
            ],
            bordered=True,
            striped=True,
            compact=True,
        ),
        divider(),
        table(
            [
                [
                    cell(["AliceDevs Core v3.37 ", emo(5456140674028019486, "⚡")], align="center", is_header=True),
                ],
            ],
            bordered=True,
            striped=True,
            compact=True,
        ),
        footer(
            [
                emo(6114074516395134769, "⚠️"),
                " Seblak pedas dapat menyebabkan mencret-mencret.",
            ]
        ),
    )

async def user_aggre(client, callback_query):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    buttons = ButtonUtils.chose_plan()
    loading = await client.send_message(
        user_id,
        "<b>Please wait...</b>",
        reply_markup=ReplyKeyboardRemove(),
    )
    await loading.delete()
    try:
        await callback_query.message.delete()
    except Exception:
        pass

    return await send_rich(
        client,
        user_id,
        heading(
            [
                emo(5373052667671093676, "💎"),
                " Seblak Ultra Pedasss",
            ],
            3,
        ),
        
        divider(),
        
        table(
            [
                [
                    cell(
                        [
                            emo(5258397811329739167, "💎"),
                            " SEBLAK DINGIN",
                        ],
                        is_header=True,
                        align="center",
                    ),
                    cell(
                        [
                            emo(5458908492687497206, "💎"),
                            " ULTRA PEDAS MENCRET",
                        ],
                        is_header=True,
                        align="center",
                    ),
                ],
                [
                    cell("Rasa"),
                    cell(
                        [
                            emo(5372824841130879657, "✅"),
                            " Ga enak",
                        ],
                        align="center",
                    ),
                ],
                [
                    cell("Gratis"),
                    cell(
                        [
                            emo(5258190433128834075, "✅"),
                            " Tidak",
                        ],
                        align="center",
                    ),
                ],
                [
                    cell("Efek Mencret"),
                    cell(
                        [
                            emo(5456140674028019486, "✅"),
                            " Iya",
                        ],
                        align="center",
                    ),
                ],
                [
                    cell("Harga per bulan"),
                    cell(
                        [
                            emo(5269720586367542578, "💰"),
                            " Rp10.000.000.000",
                        ],
                        align="center",
                    ),
                ],
            ],
            bordered=True,
            striped=True,
            compact=True,
        ),
        
        divider(),
        
        table(
            [
                [
                    cell(
                        [
                            "AliceDevs Core v3.37 ",
                            emo(5456140674028019486, "⚡"),
                        ],
                        align="center",
                        is_header=True,
                    ),
                ],
            ],
            bordered=True,
            striped=True,
            compact=True,
        ),
        
        footer(
            [
                emo(6114074516395134769, "⚠️"),
                " Seblak pedas dapat menyebabkan mencret-mencret.",
            ]
        ),
        
        reply_markup=buttons,
    )



async def chose_plan(client, callback_query):
    await callback_query.answer()
    await callback_query.message.delete()
    user_id = callback_query.from_user.id
    plan = str(callback_query.data.split()[1])

    # [BARU] produk nokos -> arahkan ke pilihan id nokos
    if plan == "nokos":
        return await tampil_pilihan_nokos(client, user_id)

    buttons = ButtonUtils.plus_minus(0, 0, plan)
    return await client.send_message(
        user_id,
        Message.TEXT_PAYMENT(0, 0, 0, plan_label(plan), 0),
        disable_web_page_preview=True,
        reply_markup=buttons,
    )


# Pilih Id Nokos Nyee
async def tampil_pilihan_nokos(client, user_id):
    rows = []
    for nokos_id in NOKOS_IDS:
        stok = len(await get_available_nokos(nokos_id))
        status = f"Stok {stok}" if stok else "Habis"
        label = f"📱 {nokos_label(nokos_id)}"
        rows.append([InlineKeyboardButton(label, callback_data=f"pilihnokos {nokos_id}")])
    rows.append([InlineKeyboardButton("❌ Batal", callback_data="planusers back")])

    return await client.send_message(
        user_id,
        f"<b>📱 Pilih ID Nokos</b>\n<blockquote><b>Harga nokos:\n{label} {Message.format_rupiah(get_nokos_price(nokos_id))}.</b></blockquote>",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def pilih_nokos(client, callback_query):
    data = callback_query.data.split()
    nokos_id = data[1] if len(data) > 1 else ""
    if nokos_id not in NOKOS_IDS:
        return await callback_query.answer("ID nokos tidak valid.", show_alert=True)

    stok = len(await get_available_nokos(nokos_id))
    if stok <= 0:
        return await callback_query.answer("Stok nokos ini sedang habis.", show_alert=True)

    await callback_query.answer()
    price = get_nokos_price(nokos_id)
    await callback_query.edit_message_text(
        f"""<b>📱 {nokos_label(nokos_id)}</b>

<blockquote><b>💵 Harga: <code>{(Message.format_rupiah(price))}</code>
📦 Stok: <code>{stok}</code></b></blockquote>

<b>Lanjutkan pembelian?</b>""",
        reply_markup=ikb(
            [
                [
                  ((" Beli Sekarang"),
                   f"buynokos {nokos_id}", ButtonStyle.PRIMARY, "5373052667671093676"),
                ],
                [
                  (("⬅️ Kembali"),
                   "planusers nokos", ButtonStyle.DANGER, "5373052667671093676"),
                ],
            ]
        ),
    )


async def beli_nokos(client, callback_query):
    await callback_query.answer()
    data = callback_query.data.split()
    user_id = callback_query.from_user.id
    nokos_id = data[1] if len(data) > 1 else ""

    if nokos_id not in NOKOS_IDS:
        return await client.send_message(user_id, "<b>ID nokos tidak valid.</b>")

    try:
        await callback_query.message.delete()
    except Exception:
        pass

    if user_id in transactions:
        return await client.send_message(
            user_id,
            "**__📑 You still have a pending transaction.__**",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancel", callback_data="batal_payment")]]
            ),
        )

    amount = get_nokos_price(nokos_id)
    if amount <= 0:
        return await client.send_message(user_id, "<b>The price cannot be 0.</b>")

    # booking 1 nomor selama pembayaran berlangsung
    number = await reserve_nokos(nokos_id, user_id)
    if not number:
        return await client.send_message(
            user_id, "<b>❌ Stok nokos ini sudah habis.</b>"
        )

    loading = await client.send_message(
        user_id, "<b><i>Memproses Pembayaran QRIS...</i></b>"
    )
    qris_path = None
    tid = None
    bukti_task = None
    paid = False
    try:
        try:
            trx = await generate_qris(amount, QRIS_EXPIRE_MINUTES)
        except CasakuError as e:
            logger.error(f"Casaku generate error (nokos): {e}")
            await loading.delete()
            if e.status in (401, 403, 429, 0, 408):
                await notify_admin(client, e.admin_message)
            return await client.send_message(user_id, f"<b>❌ {e.user_message}</b>")

        tid = trx["transactionId"]
        total_price = int(trx["totalAmount"])
        expired_min = int(trx.get("expiredInMinutes", QRIS_EXPIRE_MINUTES))
        payment_url = trx.get("payment_url")
        item_name = nokos_label(nokos_id)

        qris_path = f"qris_{user_id}_{tid[:8]}.png"
        await make_qr_image(trx["qr_string"], qris_path)

        now = datetime.now(waktu_jkt)
        expire_time = now + timedelta(minutes=expired_min)

        buttons = []
        if payment_url:
            buttons.append(
                [InlineKeyboardButton("📑 Buka Halaman Pembayaran", url=payment_url)]
            )
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="batal_payment")])

        await loading.delete()
        sent_msg = await client.send_photo(
            user_id,
            qris_path,
            caption=f"""
<b>💳 SCAN QRIS UNTUK MEMBELI</b>
<blockquote><b>
📦 Item: <code>{item_name}</code>
💵 Harga: <code>{Message.format_rupiah(amount)}</code>
💰 Total Bayar: <code>{Message.format_rupiah(total_price)}</code>
⏰ Berlaku sampai: <code>{expire_time.strftime('%H:%M')}</code>

⚠️ Bayar sesuai Total Bayar (termasuk kode unik). Pembayaran terdeteksi otomatis.
</b></blockquote>
<blockquote>© Auto Payment By: @{client.me.username}</blockquote>
""",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

        transactions[user_id] = {
            "transaction_id": tid,
            "qris_path": qris_path,
            "message_id": sent_msg.id,
            "chat_id": user_id,
        }

        def still_active():
            return transactions.get(user_id, {}).get("transaction_id") == tid

        # Minta bukti di background (untuk pemberian manual oleh admin)
        async def minta_bukti():
            try:
                bukti = await client.ask(
                    user_id,
                    "<b>🧾 Silakan kirimkan bukti pembayaran yang sudah Anda lakukan</b>",
                    filters=filters.photo,
                    timeout=expired_min * 60,
                )
                copied = await bukti.copy(
                    LOG_SELLER,
                    caption=(
                        f"<b>🧾 Bukti pembayaran NOKOS</b>\n\n"
                        f"User: <code>{user_id}</code>\n"
                        f"Item: {item_name}\n"
                        f"Harga: {Message.format_rupiah(amount)}"
                    ),
                    reply_markup=ikb(
                        [
                            [
                                (" Kasih Nokos", f"nokos {user_id} {client.me.username} {nokos_id}", ButtonStyle.PRIMARY),
                            ],
                        ]
                    ),
                )
                await dB.set_var(copied.id, f"FORWARD_{copied.id}", user_id)
                await client.send_message(
                    user_id,
                    "<b>✅ Bukti pembayaran terkirim, tunggu admin memproses.</b>",
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error kirim bukti nokos: {e}")

        bukti_task = asyncio.create_task(minta_bukti())

        try:
            status = await wait_for_payment(tid, expired_min, still_active)
        except CasakuError as e:
            bukti_task.cancel()
            logger.error(f"Casaku polling error (nokos): {e}")
            await notify_admin(client, f"Polling gagal untuk {tid}: {e.admin_message}")
            if still_active():
                await _delete_qr_message(client, sent_msg.chat.id, sent_msg.id)
                del transactions[user_id]
            return await client.send_message(
                user_id,
                "<b>⚠️ Gagal mengecek pembayaran. Jika sudah membayar, hubungi admin dengan menyertakan bukti transfer.</b>",
            )

        bukti_task.cancel()

        if status == "cancelled":
            return

        if still_active():
            del transactions[user_id]
        await _delete_qr_message(client, sent_msg.chat.id, sent_msg.id)

        if status == "paid":
            paid = True
            # nomor terjual -> hapus dari vars
            await sell_nokos(nokos_id, number)

            await client.send_message(
                LOG_SELLER,
                f"""
<b>📝「 Payment Successfully 」</b>

<blockquote><b><i>👤 User Name: <code>{callback_query.from_user.first_name}</code>
🆔 User ID: <code>{str(user_id)[:3]}######</code>
📦 Item: <code>{item_name}</code>
📱 Nomor: <code>{number}</code>
💵 Price: <code>{Message.format_rupiah(amount)}</code>
💰 Paid: <code>{Message.format_rupiah(total_price)}</code>
🧾 Trx: <code>{tid}</code>
📅 Date: <code>{now.strftime('%d-%m-%Y')}</code>
⏰ Time: <code>{datetime.now(waktu_jkt).strftime('%H:%M')}</code></i></b></blockquote>

<blockquote>© Auto Payment @{client.me.username}</blockquote>
""",
            )

            # kirim nomornya otomatis ke pembeli
            try:
                await kirim_nomor_nokos(client, user_id, nokos_id, number)
            except Exception as e:
                logger.error(f"Gagal kirim nokos: {traceback.format_exc()}")
                await notify_admin(
                    client,
                    f"Gagal kirim nomor <code>{number}</code> ({item_name}) ke <code>{user_id}</code>: {e}. Kirim manual.",
                )
                await client.send_message(
                    user_id,
                    "<b>⚠️ Nomor gagal dikirim otomatis, admin akan mengirimkannya manual.</b>",
                )
        else:
            await client.send_message(
                user_id,
                "<b>⌛ Waktu pembayaran habis atau transaksi dibatalkan. Silakan buat transaksi baru.</b>",
            )

    except Exception:
        logger.error(f"ERROR beli_nokos: {traceback.format_exc()}")
        if bukti_task:
            bukti_task.cancel()
        if transactions.get(user_id, {}).get("transaction_id") == tid:
            transactions.pop(user_id, None)
        await client.send_message(
            user_id, "<b>An error occurred, please try again.</b>"
        )
    finally:
        # kalau tidak jadi terbayar, lepas booking nomor supaya bisa dijual lagi
        if not paid:
            release_nokos(number)
        _remove_file(qris_path)


async def kurang_tambah(client, callback_query):
    try:
        data = callback_query.data.split()
        QUERY = data[0]
        BULAN = int(data[1])
        PLAN = str(data[-1])

        if QUERY == "kurang":
            if BULAN > 1:
                BULAN -= 1
        elif QUERY == "tambah":
            if BULAN < 12:
                BULAN += 1

        HARGA = PRICES[normalize_plan(PLAN)]
        DISKON = 0
        TOTAL_HARGA = get_price(PLAN, BULAN) - DISKON

        buttons = ButtonUtils.plus_minus(BULAN, TOTAL_HARGA, PLAN)
        await callback_query.edit_message_text(
            Message.TEXT_PAYMENT(HARGA, TOTAL_HARGA, BULAN, plan_label(PLAN), DISKON),
            disable_web_page_preview=True,
            reply_markup=buttons,
        )
    except Exception:
        logger.error(f"ERROR kurang_tambah: {traceback.format_exc()}")


async def confirm_pay(client: Message, callback_query):
    await callback_query.answer()
    data = callback_query.data.split()
    user_id = callback_query.from_user.id

    plan = str(data[-1])
    PLAN = plan_label(plan)
    unit = PRICES[normalize_plan(plan)]

    try:
        val = int(data[1])
    except (IndexError, ValueError):
        val = 0
    # data[1] berisi TOTAL HARGA (mis. 10000), bukan jumlah bulan
    month = val // unit if val >= unit else val

    await callback_query.message.delete()

    if not 1 <= month <= 12:
        return await client.send_message(user_id, "<b>Jumlah bulan tidak valid.</b>")
    amount = get_price(plan, month)
    if amount <= 0:
        return await client.send_message(user_id, "<b>The price cannot be 0.</b>")
    if user_id in transactions:
        return await callback_query.message.reply(
            "**__📑 You still have a pending transaction.__**",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancel", callback_data="batal_payment")]]
            ),
        )

    loading = await callback_query.message.reply(
        "<b><i>Memproses Pembayaran QRIS...</i></b>"
    )
    qris_path = None
    tid = None
    bukti_task = None
    try:
        try:
            trx = await generate_qris(amount, QRIS_EXPIRE_MINUTES)
        except CasakuError as e:
            logger.error(f"Casaku generate error: {e}")
            await loading.delete()
            if e.status in (401, 403, 429, 0, 408):
                await notify_admin(client, e.admin_message)
            return await client.send_message(user_id, f"<b>❌ {e.user_message}</b>")

        tid = trx["transactionId"]
        total_price = int(trx["totalAmount"])
        expired_min = int(trx.get("expiredInMinutes", QRIS_EXPIRE_MINUTES))
        payment_url = trx.get("payment_url")
        item_name = f"Seblak Mencret {month} Months"

        qris_path = f"qris_{user_id}_{tid[:8]}.png"
        await make_qr_image(trx["qr_string"], qris_path)

        now = datetime.now(waktu_jkt)
        expire_time = now + timedelta(minutes=expired_min)

        buttons = []
        if payment_url:
            buttons.append(
                [InlineKeyboardButton("📑 Buka Halaman Pembayaran", url=payment_url)]
            )
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="batal_payment")])

        await loading.delete()
        sent_msg = await callback_query.message.reply_photo(
            qris_path,
            caption=f"""
<b>💳 SCAN QRIS UNTUK MEMBELI</b>
<blockquote><b>
📦 Item: <code>{item_name}</code>
💵 Harga: <code>{Message.format_rupiah(amount)}</code>
💰 Total Bayar: <code>{Message.format_rupiah(total_price)}</code>
⏰ Berlaku sampai: <code>{expire_time.strftime('%H:%M')}</code>

⚠️ Bayar Seblak sesuai Total Bayar (termasuk kode unik). Pembayaran terdeteksi otomatis.
</b></blockquote>
<blockquote>© Auto Payment By: @{client.me.username}</blockquote>
""",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

        # Daftarkan transaksi dulu, supaya tombol Cancel langsung berfungsi
        transactions[user_id] = {
            "transaction_id": tid,
            "qris_path": qris_path,
            "message_id": sent_msg.id,
            "chat_id": callback_query.message.chat.id,
        }

        def still_active():
            return transactions.get(user_id, {}).get("transaction_id") == tid

        # Minta bukti di background, supaya polling tidak tertahan
        async def minta_bukti():
            try:
                bukti = await client.ask(
                    user_id,
                    "<b>🧾 Silakan kirimkan bukti pembayaran yang sudah Anda lakukan</b>",
                    filters=filters.photo,
                    timeout=expired_min * 60,
                )
                copied = await bukti.copy(
                    LOG_SELLER,
                    caption=(
                        f"<b>🧾 Bukti pembayaran</b>\n\n"
                        f"User: <code>{user_id}</code>\n"
                        f"Plan: {PLAN}\n"
                        f"Harga: {Message.format_rupiah(amount)}"
                    ),
                    reply_markup=ikb(
                        [
                            [
                                (" Akses VIP", f"vip {user_id} {client.me.username} {plan}", ButtonStyle.PRIMARY),
                                (" Akses Ubot", f"ubot {user_id} {client.me.username} {plan} {month}", ButtonStyle.SUCCESS),
                            ],
                        ]
                    ),
                )
                # supaya admin bisa membalas pembeli lewat outgoing_reply
                await dB.set_var(copied.id, f"FORWARD_{copied.id}", user_id)
                await client.send_message(
                    user_id,
                    "<b>✅ Bukti pembayaran terkirim, tunggu admin memproses.</b>",
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error kirim bukti: {e}")
            

        bukti_task = asyncio.create_task(minta_bukti())

        # Polling status pembayaran ke Casaku
        try:
            status = await wait_for_payment(tid, expired_min, still_active)
        except CasakuError as e:
            bukti_task.cancel()
            logger.error(f"Casaku polling error: {e}")
            await notify_admin(client, f"Polling gagal untuk {tid}: {e.admin_message}")
            if still_active():
                await _delete_qr_message(client, sent_msg.chat.id, sent_msg.id)
                del transactions[user_id]
            return await client.send_message(
                user_id,
                "<b>⚠️ Gagal mengecek pembayaran. Jika sudah membayar, hubungi admin dengan menyertakan bukti transfer.</b>",
            )

        bukti_task.cancel()  # pembayaran selesai/batal/expired, berhenti menunggu foto

        if status == "cancelled":
            return
          
        if still_active():
            del transactions[user_id]
        await _delete_qr_message(client, sent_msg.chat.id, sent_msg.id)

        if status == "paid":
            await client.send_message(
                LOG_SELLER,
                f"""
<b>📝「 Payment Successfully 」</b>

<blockquote><b><i>👤 User Name: <code>{callback_query.from_user.first_name}</code>
🆔 User ID: <code>{str(user_id)[:3]}######</code>
📦 Item: <code>{item_name}</code>
💵 Price: <code>{Message.format_rupiah(amount)}</code>
💰 Paid: <code>{Message.format_rupiah(total_price)}</code>
🧾 Trx: <code>{tid}</code>
📅 Date: <code>{now.strftime('%d-%m-%Y')}</code>
⏰ Time: <code>{datetime.now(waktu_jkt).strftime('%H:%M')}</code></i></b></blockquote>

<blockquote>© Auto Payment @{client.me.username}</blockquote>
""",
            )
            await add_transaction(user_id, month, plan)
            if user_id not in AKSES_DEPLOY:
                AKSES_DEPLOY.append(user_id)

            # [UBAH] tombol "Mulai Buat Userbot" HANYA muncul untuk produk userbot.
            # Pembelian channel VIP tidak lagi menampilkan tombol ini.
            if get_product(plan) == "ubot":
                await client.send_message(
                    user_id,
                    "<b><i>✅ Payment successful.\nClick the button below to create your UserBot.</i></b>",
                    reply_markup=ReplyKeyboardMarkup(
                        [[KeyboardButton("✨ Mulai Buat Userbot")]],
                        resize_keyboard=True,
                        one_time_keyboard=True,
                    ),
                )

            # Kirim link channel private sekali klik (auto revoke setelah expired)
            try:
                await kirim_link_vip(client, user_id, plan)
            except Exception as e:
                logger.error(f"Gagal kirim link VIP: {traceback.format_exc()}")
                await notify_admin(
                    client,
                    f"Gagal membuat link VIP untuk <code>{user_id}</code>: {e}",
                )
                await client.send_message(
                    user_id,
                    "<b>⚠️ Link channel gagal dibuat, admin akan mengirimkannya manual.</b>",
                )
        else:
            await client.send_message(
                user_id,
                "<b>⌛ Waktu pembayaran habis atau transaksi dibatalkan. Silakan buat transaksi baru.</b>",
            )

    except Exception:
        logger.error(f"ERROR confirm_pay: {traceback.format_exc()}")
        if bukti_task:
            bukti_task.cancel()
        if transactions.get(user_id, {}).get("transaction_id") == tid:
            transactions.pop(user_id, None)
        _remove_file(qris_path)
        return await client.send_message(
            user_id, "<b>An error occurred, please try again.</b>"
        )


async def cancel_payment(client, callback_query):
    user_id = callback_query.from_user.id

    tx = transactions.pop(user_id, None)
    if not tx:
        await callback_query.answer()
        return await callback_query.message.reply(
            "**__❌ Tidak Ada Transaksi Yang Aktif__**"
        )

    _remove_file(tx.get("qris_path"))
    try:
        await cancel_transaction(tx["transaction_id"])
    except CasakuError as e:
        logger.warning(f"Cancel Casaku gagal: {e}")
    await _delete_qr_message(client, tx["chat_id"], tx["message_id"])

    await client.send_message(
        user_id, "**__📑 Transaksi Berhasil Dibatalkan.__**"
    )
    # kembali ke menu pilihan produk
    return await user_aggre(client, callback_query)


async def kasih_vip(client, callback_query):
    """Tombol admin '💎 Akses VIP': kirim link channel sesuai plan yang dibeli."""
    data = callback_query.data.split()
    user_ids = int(data[1])
    if len(data) < 4:
        return await callback_query.answer(
            "Plan tidak ada di tombol ini (bukti lama).", show_alert=True
        )
    plan = data[3]

    try:
        await kirim_link_vip(client, user_ids, plan)
    except Exception as e:
        logger.error(f"ERROR kasih_vip: {traceback.format_exc()}")
        return await callback_query.answer(
            f"Gagal membuat link: {e}", show_alert=True
        )

    await callback_query.message.edit(
        f"**✅ Link channel {plan_label(plan)} sudah dikirim ke pembeli**"
    )


async def kasih_ubot(client, callback_query):
    await callback_query.answer()
    data = callback_query.data.split()
    user_ids = int(data[1])
    plan = str(data[3])
    month = int(data[4])
    PLAN = plan_label(plan)

    await add_transaction(user_ids, month, plan)
    if user_ids not in AKSES_DEPLOY:
        AKSES_DEPLOY.append(user_ids)

    await client.send_message(
        user_ids,
        f"<b>✅ Akses userbot premium ({PLAN}) sudah diberikan! Silahkan klik tombol di bawah untuk membuat userbot kamu.</b>",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("✨ Mulai Buat Userbot")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    await callback_query.message.edit(
        f"<b>✅ Akses {PLAN} ({month} bulan) telah diberikan ke user <code>{user_ids}</code>.</b>"
    )


# [BARU] Tombol admin "Kasih Nokos": ambil 1 nomor dari vars lalu kirim ke pembeli
async def kasih_nokos(client, callback_query):
    data = callback_query.data.split()
    if len(data) < 4:
        return await callback_query.answer(
            "ID nokos tidak ada di tombol ini (bukti lama).", show_alert=True
        )
    user_ids = int(data[1])
    nokos_id = data[3]

    if nokos_id not in NOKOS_IDS:
        return await callback_query.answer("ID nokos tidak valid.", show_alert=True)

    number = await take_nokos(nokos_id)
    if not number:
        return await callback_query.answer(
            f"Stok {nokos_label(nokos_id)} habis.", show_alert=True
        )

    try:
        await kirim_nomor_nokos(client, user_ids, nokos_id, number)
    except Exception as e:
        logger.error(f"ERROR kasih_nokos: {traceback.format_exc()}")
        await restock_nokos(nokos_id, number)  # kembalikan ke vars
        return await callback_query.answer(
            f"Gagal kirim nomor: {e}", show_alert=True
        )

    await callback_query.message.edit(
        f"**✅ {nokos_label(nokos_id)} ({number}) sudah dikirim ke pembeli**"
    )


async def qris_cmd(client, message):
    em = Emoji(client)
    await em.get()

    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return await message.reply(
            f"{em.gagal}**Sorry, this feature is only for the Owner.**"
        )

    if user_id in transactions:
        return await message.reply(
            f"""
<b><i>{em.gagal}You still have an ongoing transaction.
{em.warn}You can cancel it using <code>.cancelpay</code>.</i></b>
"""
        )

    args = message.text.split(maxsplit=1)
    try:
        amount_str, description = args[1].split(",", maxsplit=1)
        amount = int(amount_str.strip())
        description = description.strip()
        if amount <= 0:
            raise ValueError
    except (IndexError, ValueError):
        return await message.reply(
            f"{em.gagal}**Incorrect format. Use:** <code>.pay amount, description</code>"
        )

    loading = await message.reply(f"{em.proses}**Prosesing..**")
    qris_path = None
    tid = None
    try:
        try:
            trx = await generate_qris(amount, QRIS_EXPIRE_MINUTES)
        except CasakuError as e:
            await loading.delete()
            return await message.reply(f"{em.gagal}**{e.admin_message}**")

        tid = trx["transactionId"]
        total_amount = int(trx["totalAmount"])
        expired_min = int(trx.get("expiredInMinutes", QRIS_EXPIRE_MINUTES))
        formatted_time = (
            datetime.now(waktu_jkt) + timedelta(minutes=expired_min)
        ).strftime("%H:%M")

        qris_path = f"qris_{user_id}_{tid[:8]}.png"
        await make_qr_image(trx["qr_string"], qris_path)

        await loading.delete()
        sent_message = await message.reply_photo(
            qris_path,
            caption=f"""
<b>📃「 Waiting Payment 」</b>

<blockquote><b><i>{em.profil}Item: <code>{description}</code>
{em.net}Price: <code>Rp{amount:,}</code>
{em.speed}Total Payment: <code>Rp{total_amount:,}</code>
{em.warn}Expiration Time: <code>{formatted_time}</code>

Please scan the QRIS above to complete the payment.
If you encounter any issues, contact <a href='tg://user?id={OWNER_ID}'>ADMIN</a>
Type <code>.cancelpay</code> to cancel the transaction.</i></b></blockquote>

<blockquote>© Auto Payment @{bot.me.username}</blockquote>
""",
        )
        _remove_file(qris_path)

        transactions[user_id] = {
            "transaction_id": tid,
            "qris_path": qris_path,
            "message_id": sent_message.id,
            "chat_id": message.chat.id,
        }

        def still_active():
            return transactions.get(user_id, {}).get("transaction_id") == tid

        try:
            status = await wait_for_payment(tid, expired_min, still_active)
        except CasakuError as e:
            if still_active():
                del transactions[user_id]
            await _delete_qr_message(client, message.chat.id, sent_message.id)
            return await message.reply(f"{em.gagal}**{e.admin_message}**")

        if status == "cancelled":
            return

        if still_active():
            del transactions[user_id]
        await _delete_qr_message(client, message.chat.id, sent_message.id)

        if status == "paid":
            await message.reply(
                f"""
<blockquote><b><i>{em.sukses}Payment received successfully!

{em.profil}Item: <code>{description}</code>
{em.net}Price: <code>Rp{amount:,}</code>
{em.speed}Total Paid: <code>Rp{total_amount:,}</code></i></b></blockquote>
"""
            )
        else:
            await message.reply(
                f"{em.gagal}**Transaction canceled due to expiration.**"
            )
    except Exception:
        logger.error(f"ERROR qris_cmd: {traceback.format_exc()}")
        if transactions.get(user_id, {}).get("transaction_id") == tid:
            transactions.pop(user_id, None)
        _remove_file(qris_path)
        await message.reply(f"{em.gagal}**An error occurred, please try again.**")


async def cancelpay_cmd(client, message):
    em = Emoji(client)
    await em.get()

    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return await message.reply(
            f"{em.gagal}**Sorry, this feature is only for the Owner.**"
        )

    tx = transactions.pop(user_id, None)
    if not tx:
        return await message.reply(
            f"{em.warn}**There is no active transaction to cancel.**"
        )

    _remove_file(tx.get("qris_path"))
    try:
        await cancel_transaction(tx["transaction_id"])
    except CasakuError as e:
        logger.warning(f"Cancel Casaku gagal: {e}")
    await _delete_qr_message(client, tx["chat_id"], tx["message_id"])

    return await message.reply(
        f"{em.sukses}**Transaction has been successfully canceled.**"
    )
