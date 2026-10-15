######################################################
# PAY2 - Telegram Premium, Stars, Netflix, Suntik GC/CH
# Pakai payment Casaku dari payment_command.py (tanpa copy ulang)
######################################################

import asyncio
import traceback
from datetime import datetime, timedelta

from pyrogram import filters
from pyrogram.enums import ButtonStyle
from pyrogram.helpers import ikb, send_rich
from pyrogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Markup

from .payment_command import (
    QRIS_EXPIRE_MINUTES, CasakuError, _delete_qr_message, _remove_file,
    generate_qris, make_qr_image, menu_blocks, notify_admin, transactions,
    wait_for_payment, waktu_jkt,
)
from config import LOG_SELLER, OWNER_ID
from database import dB
from helpers import ButtonUtils, Message
from logs import logger

rp = Message.format_rupiah

# style + custom emoji tombol (spasi di depan teks = tempat emoji)
P, S, D = ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER
E_PRIMARY = "5373052667671093676"
E_OK = "6296367896398399651"
E_BATAL = "5260293700088511294"
E_ITEM = "5258397811329739167"
E_STARS = "6255759783773605832"
E_HARGA = "5461139036708033234"
E_PREM = "6298747815086524010"
E_PAKET = "5231391525123934586"
E_NETFLIX = "5318911503938634641"
E_BELI = "6269136309093143551"
E_PLUS = "5226945370684140473"
E_MINUS = "5229113891081956317"


def ce(emoji_id, fallback):
    """Emoji premium (custom) di dalam teks HTML.
    Kalau parser forkmu memakai <tg-emoji emoji-id="...">, cukup ubah di sini."""
    return f'<emoji id="{emoji_id}">{fallback}</emoji>'


PREM, STAR, NFX = ce(E_PREM, "💎"), ce(E_STARS, "⭐"), ce(E_NETFLIX, "🎬")
HARGA, PAKET = ce(E_HARGA, "💵"), ce(E_PAKET, "📦")
ICON = {"tp": PREM, "st": STAR, "nf": NFX}  # emoji per jenis item
BATAL = (" Batal", "planusers back", D, E_BATAL)  # kembali ke menu pilihan produk (edit pesan)
async def pay2_back(client, cq):
    """Tombol Batal: kembali ke menu pilihan produk yang SAMA dengan user_aggre (rich).
    Coba edit pesan dulu; kalau fork tidak punya fungsi edit rich, fallback hapus + kirim ulang."""
    logger.info(f"pay2_back dipanggil oleh {cq.from_user.id}")
    await cq.answer()
    markup = ButtonUtils.chose_plan()
    try:
        # Bot API 10.1: rich message diedit lewat editMessageText(rich_message=...)
        from pyrogram.types import InputRichMessage

        return await cq.edit_message_text(
            rich_message=InputRichMessage(blocks=list(menu_blocks())),
            reply_markup=markup,
        )
    except Exception as e:
        logger.warning(f"pay2_back: edit rich gagal ({e!r}), kirim ulang menu")
    try:
        await cq.message.delete()
    except Exception:
        pass
    await send_rich(client, cq.from_user.id, *menu_blocks(), reply_markup=markup)


def kb(rows, url_rows=()):
    """ikb untuk tombol callback; url_rows (InlineKeyboardButton url) ditaruh paling atas."""
    markup = ikb(rows)
    return Markup(list(url_rows) + markup.inline_keyboard) if url_rows else markup

# ------------------------------------------------------------------
# DAFTAR PRODUK  (ubah harga di sini)
# ------------------------------------------------------------------
TELPREM = {  # key: (label, harga)
    "gift3": ("Gift 3 Bulan", 165000),
    "gift6": ("Gift 6 Bulan", 230000),
    "gift12": ("Gift 12 Bulan", 390000),
    "login1": ("Login 1 Bulan", 60000),
    "login12": ("Login 12 Bulan", 300000),
}

# (jumlah stars, harga) sesuai screenshot paket Telegram
STARS = [
    (100, 31499), (150, 45999), (250, 74999), (350, 103999), (500, 146999),
    (750, 219999), (1000, 289999), (1500, 433999), (2500, 719999),
    (5000, 1439999), (10000, 2899999), (25000, 7199999), (50000, 14399999),
    (100000, 28999999), (150000, 42999999),
]

NETFLIX_PRICE = 2  # 1 bulan full garansi
NF_VAR = "netflix_stock"  # 1 akun per baris, format email:password

# ------------------------------------------------------------------
# STOK NETFLIX (sistem sama seperti nokos: booking saat bayar, hapus saat terjual)
# ------------------------------------------------------------------
nf_lock = asyncio.Lock()
nf_reserved = {}  # akun -> user_id


async def nf_list():
    raw = await dB.get_var(OWNER_ID, NF_VAR)
    return [x.strip() for x in str(raw or "").split("\n") if x.strip()]


async def nf_save(items):
    await dB.set_var(OWNER_ID, NF_VAR, "\n".join(items))


async def nf_available():
    return [a for a in await nf_list() if a not in nf_reserved]


async def nf_reserve(user_id):
    async with nf_lock:
        for acc in await nf_list():
            if acc not in nf_reserved:
                nf_reserved[acc] = user_id
                return acc
    return None


async def nf_sell(acc):
    async with nf_lock:
        items = await nf_list()
        if acc in items:
            items.remove(acc)
            await nf_save(items)
        nf_reserved.pop(acc, None)


async def nf_take():  # tombol manual admin
    async with nf_lock:
        items = await nf_list()
        for acc in items:
            if acc not in nf_reserved:
                items.remove(acc)
                await nf_save(items)
                return acc
    return None


async def nf_restock(acc):
    async with nf_lock:
        items = await nf_list()
        if acc not in items:
            items.append(acc)
            await nf_save(items)


async def nf_cmd(client, message):
    """/addnf email:pass ...  |  /delnf email:pass ...  |  /stoknf  (owner)"""
    if message.from_user.id != OWNER_ID:
        return await message.reply("<b>❌ Perintah ini hanya untuk Owner.</b>")
    parts = message.text.split()
    cmd, args = parts[0].lstrip("/.").lower(), parts[1:]
    items = await nf_list()

    if cmd == "stoknf":
        body = "\n".join(f"<code>{a}</code>" for a in items) or "Kosong"
        return await message.reply(f"<b>📊 Stok Netflix: {len(items)}</b>\n{body}")
    if not args:
        return await message.reply("<b>Format:</b> <code>/addnf email:pass email2:pass2</code>")

    if cmd == "addnf":
        new = [a for a in args if a not in items]
        await nf_save(items + new)
        return await message.reply(f"<b>✅ Ditambahkan {len(new)} akun. Stok: {len(items) + len(new)}</b>")
    if cmd == "delnf":
        left = [a for a in items if a not in args]
        await nf_save(left)
        return await message.reply(f"<b>🗑️ Dihapus {len(items) - len(left)} akun. Stok: {len(left)}</b>")


async def kirim_netflix(client, user_id, acc):
    await client.send_message(
        user_id,
        f"""<b>✅ Pembayaran Berhasil</b>

<blockquote><b>{NFX} Produk: Netflix 1 Bulan Full Garansi
🔑 Akun: <code>{acc}</code></b></blockquote>

<blockquote><b>Jangan ubah email/password. Jika ada kendala, hubungi admin.</b></blockquote>""",
    )


# ------------------------------------------------------------------
# MENU PRODUK
# dipanggil dari chose_plan() di payment_command.py:
#   if plan in ("telprem", "stars", "netflix", "suntik"):
#       return await pay2_menu(client, user_id, plan)
# ------------------------------------------------------------------
def item_info(kind, key):
    if kind == "tp":
        label, price = TELPREM[key]
        return f"Telegram Premium {label}", price
    if kind == "st":
        stars, price = STARS[int(key)]
        return f"{stars:,} Stars", price
    return "Netflix 1 Bulan Full Garansi", NETFLIX_PRICE


def stars_view(i):
    stars, price = STARS[i]
    text = (
        f"<b>{STAR} Beli Telegram Stars</b>\n"
        f"<blockquote><b>{PAKET} Paket: <code>{stars:,}</code> Stars\n"
        f"{HARGA} Harga: <code>{rp(price)}</code></b></blockquote>\n"
        "<i>Tekan Kurang / Tambah untuk ubah jumlah.</i>"
    )
    markup = ikb([
        [(" Kurang", f"p2star {max(i - 1, 0)}", P, E_MINUS),
         (" Tambah", f"p2star {min(i + 1, len(STARS) - 1)}", P, E_PLUS)],
        [(f" Beli • {rp(price)}", f"p2buy st {i}", S, E_BELI)],
        [BATAL],
    ])
    return text, markup


async def pay2_menu(client, user_id, plan):
    if plan == "telprem":
        rows = [[(f" {label} • {rp(price)}", f"p2buy tp {key}", P, E_PREM)]
                for key, (label, price) in TELPREM.items()]
        return await client.send_message(
            user_id, f"<b>{PREM} Telegram Premium</b>\n<blockquote><b>{PAKET} Pilih paket:</b></blockquote>",
            reply_markup=kb(rows + [[BATAL]]))

    if plan == "stars":
        text, markup = stars_view(0)
        return await client.send_message(user_id, text, reply_markup=markup)

    if plan == "netflix":
        stok = len(await nf_available())
        rows = [[(f" Beli • {rp(NETFLIX_PRICE)}", "p2buy nf 0", S, E_BELI)]] if stok else []
        return await client.send_message(
            user_id,
            f"<b>{NFX} Netflix 1 Bulan Full Garansi</b>\n<blockquote><b>{HARGA} Harga: <code>{rp(NETFLIX_PRICE)}</code>\n"
            f"{PAKET} Stok: <code>{stok or 'Habis'}</code></b></blockquote>",
            reply_markup=kb(rows + [[BATAL]]))

    if plan == "suntik":
        return await client.send_message(
            user_id,
            f"<b>{PAKET} Suntik Member GC/CH</b>\n<blockquote><b>{HARGA} Order manual, hubungi owner untuk harga & jumlah.</b></blockquote>",
            reply_markup=kb([[BATAL]], [[Btn("💬 Hubungi Owner", url=f"tg://user?id={OWNER_ID}")]]))


# ------------------------------------------------------------------
# CALLBACK USER: p2star <idx> | p2buy <kind> <key>
# ------------------------------------------------------------------
async def pay2_callback(client, cq):
    d = cq.data.split()
    if d[0] == "p2star":
        await cq.answer()
        try:
            text, markup = stars_view(int(d[1]))
            await cq.edit_message_text(text, reply_markup=markup)
        except Exception:
            pass  # sudah di batas paket / tidak berubah
        return
    if d[0] == "p2buy":
        return await checkout(client, cq, d[1], d[2])


# ------------------------------------------------------------------
# CHECKOUT QRIS (satu alur untuk semua produk)
# ------------------------------------------------------------------
async def checkout(client, cq, kind, key):
    user_id = cq.from_user.id
    name, amount = item_info(kind, key)

    if user_id in transactions:
        return await cq.answer("Kamu masih punya transaksi pending, batalkan dulu.", show_alert=True)

    acc = None
    if kind == "nf":
        acc = await nf_reserve(user_id)
        if not acc:
            return await cq.answer("Stok Netflix habis.", show_alert=True)
    await cq.answer()
    try:
        await cq.message.delete()
    except Exception:
        pass

    # tombol akses manual admin (di bukti & log pembayaran)
    if kind == "nf":
        admin_kb = ikb([[(" Kasih Netflix", f"p2nf {user_id}", P, E_NETFLIX)]])
    else:
        lbl, emo_id = (" Proses Telprem", E_PREM) if kind == "tp" else (" Kirim Stars", E_STARS)
        admin_kb = ikb([[(lbl, f"p2done {user_id} {kind} {key}", P, emo_id)]])

    loading = await client.send_message(user_id, "<b><i>Memproses Pembayaran QRIS...</i></b>")
    qris_path = tid = bukti_task = None
    paid = False
    try:
        try:
            trx = await generate_qris(amount, QRIS_EXPIRE_MINUTES)
        except CasakuError as e:
            logger.error(f"Casaku generate error (pay2): {e}")
            await loading.delete()
            if e.status in (401, 403, 429, 0, 408):
                await notify_admin(client, e.admin_message)
            return await client.send_message(user_id, f"<b>❌ {e.user_message}</b>")

        tid = trx["transactionId"]
        total = int(trx["totalAmount"])
        exp_min = int(trx.get("expiredInMinutes", QRIS_EXPIRE_MINUTES))
        now = datetime.now(waktu_jkt)
        qris_path = f"qris_{user_id}_{tid[:8]}.png"
        await make_qr_image(trx["qr_string"], qris_path)

        url_rows = [[Btn("📑 Buka Halaman Pembayaran", url=trx["payment_url"])]] if trx.get("payment_url") else []
        qris_kb = kb([[(" Cancel", "batal_payment", D, E_BATAL)]], url_rows)

        await loading.delete()
        sent = await client.send_photo(
            user_id, qris_path,
            caption=f"""
<b>💳 SCAN QRIS UNTUK MEMBELI</b>
<blockquote><b>
{ICON[kind]} Item: <code>{name}</code>
{HARGA} Harga: <code>{rp(amount)}</code>
{HARGA} Total Bayar: <code>{rp(total)}</code>
⏰ Berlaku sampai: <code>{(now + timedelta(minutes=exp_min)).strftime('%H:%M')}</code>

⚠️ Bayar sesuai Total Bayar (termasuk kode unik). Pembayaran terdeteksi otomatis.
</b></blockquote>
<blockquote>© Auto Payment By: @{client.me.username}</blockquote>
""",
            reply_markup=qris_kb,
        )
        transactions[user_id] = {
            "transaction_id": tid, "qris_path": qris_path,
            "message_id": sent.id, "chat_id": user_id,
        }

        def still_active():
            return transactions.get(user_id, {}).get("transaction_id") == tid

        async def minta_bukti():  # background, untuk pemberian manual admin
            try:
                bukti = await client.ask(
                    user_id, "<b>🧾 Silakan kirimkan bukti pembayaran yang sudah Anda lakukan</b>",
                    filters=filters.photo, timeout=exp_min * 60)
                copied = await bukti.copy(
                    LOG_SELLER,
                    caption=f"<b>🧾 Bukti pembayaran</b>\n\nUser: <code>{user_id}</code>\n"
                            f"{ICON[kind]} Item: {name}\n{HARGA} Harga: {rp(amount)}",
                    reply_markup=admin_kb)
                await dB.set_var(copied.id, f"FORWARD_{copied.id}", user_id)
                await client.send_message(user_id, "<b>✅ Bukti pembayaran terkirim, tunggu admin memproses.</b>")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error kirim bukti pay2: {e}")

        bukti_task = asyncio.create_task(minta_bukti())

        try:
            status = await wait_for_payment(tid, exp_min, still_active)
        except CasakuError as e:
            bukti_task.cancel()
            await notify_admin(client, f"Polling gagal untuk {tid}: {e.admin_message}")
            if still_active():
                await _delete_qr_message(client, sent.chat.id, sent.id)
                del transactions[user_id]
            return await client.send_message(
                user_id, "<b>⚠️ Gagal mengecek pembayaran. Jika sudah membayar, hubungi admin dengan bukti transfer.</b>")

        bukti_task.cancel()
        if status == "cancelled":
            return
        if still_active():
            del transactions[user_id]
        await _delete_qr_message(client, sent.chat.id, sent.id)

        if status != "paid":
            return await client.send_message(
                user_id, "<b>⌛ Waktu pembayaran habis atau transaksi dibatalkan. Silakan buat transaksi baru.</b>")

        paid = True
        if kind == "nf":
            await nf_sell(acc)
        await client.send_message(
            LOG_SELLER,
            f"""
<b>📝「 Payment Successfully 」</b>

<blockquote><b><i>👤 User Name: <code>{cq.from_user.first_name}</code>
🆔 User ID: <code>{str(user_id)[:3]}######</code>
{ICON[kind]} Item: <code>{name}</code>{f"{chr(10)}🔑 Akun: <code>{acc}</code>" if acc else ""}
{HARGA} Price: <code>{rp(amount)}</code>
{HARGA} Paid: <code>{rp(total)}</code>
🧾 Trx: <code>{tid}</code>
📅 {now.strftime('%d-%m-%Y')} ⏰ {datetime.now(waktu_jkt).strftime('%H:%M')}</i></b></blockquote>

<blockquote>© Auto Payment @{client.me.username}</blockquote>
""",
            reply_markup=None if kind == "nf" else admin_kb,
        )

        if kind == "nf":  # otomatis kirim akun
            try:
                await kirim_netflix(client, user_id, acc)
            except Exception as e:
                logger.error(f"Gagal kirim netflix: {traceback.format_exc()}")
                await notify_admin(client, f"Gagal kirim akun <code>{acc}</code> ke <code>{user_id}</code>: {e}. Kirim manual.")
                await client.send_message(user_id, "<b>⚠️ Akun gagal dikirim otomatis, admin akan mengirimkannya manual.</b>")
        else:  # telprem / stars -> admin proses manual
            await client.send_message(
                user_id,
                f"<b>✅ Pembayaran Berhasil</b>\n<blockquote><b>{ICON[kind]} Item: {name}\n"
                "Admin akan segera memproses. Kirim username/data tujuan ke admin.</b></blockquote>",
                reply_markup=Markup([[Btn("💬 Hubungi Admin", url=f"tg://user?id={OWNER_ID}")]]),
            )

    except Exception:
        logger.error(f"ERROR pay2 checkout: {traceback.format_exc()}")
        if bukti_task:
            bukti_task.cancel()
        if transactions.get(user_id, {}).get("transaction_id") == tid:
            transactions.pop(user_id, None)
        await client.send_message(user_id, "<b>An error occurred, please try again.</b>")
    finally:
        if not paid and acc:  # batal/expired/error -> stok bisa dijual lagi
            nf_reserved.pop(acc, None)
        _remove_file(qris_path)


# ------------------------------------------------------------------
# CALLBACK ADMIN: p2nf <uid> | p2done <uid> <kind> <key>
# ------------------------------------------------------------------
async def _mark(cq, text):
    try:
        await cq.message.edit_text(text)
    except Exception:
        await cq.message.edit_caption(text)


async def pay2_admin(client, cq):
    d = cq.data.split()
    uid = int(d[1])

    if d[0] == "p2nf":  # ambil 1 akun dari stok lalu kirim
        acc = await nf_take()
        if not acc:
            return await cq.answer("Stok Netflix habis.", show_alert=True)
        try:
            await kirim_netflix(client, uid, acc)
        except Exception as e:
            logger.error(f"ERROR p2nf: {traceback.format_exc()}")
            await nf_restock(acc)
            return await cq.answer(f"Gagal kirim akun: {e}", show_alert=True)
        return await _mark(cq, f"**✅ Netflix ({acc}) sudah dikirim ke pembeli**")

    if len(d) < 4:
        return await cq.answer("Data item tidak ada di tombol ini (bukti lama).", show_alert=True)
    name, _ = item_info(d[2], d[3])
    try:
        await client.send_message(uid, f"<b>✅ Pesanan {name} sudah diproses admin. Terima kasih!</b>")
    except Exception as e:
        return await cq.answer(f"Gagal kirim ke pembeli: {e}", show_alert=True)
    await _mark(cq, f"**✅ {name} ditandai selesai untuk user** <code>{uid}</code>")


# ------------------------------------------------------------------
# REGISTER HANDLER (contoh, sesuaikan dengan cara kamu daftar handler)
# ------------------------------------------------------------------
# bot.on_callback_query(filters.regex(r"^p2(star|buy) "))(pay2_callback)
# bot.on_callback_query(filters.regex(r"^p2(nf|done) "))(pay2_admin)
# bot.on_message(filters.command(["addnf", "delnf", "stoknf"]))(nf_cmd)
