import asyncio
import re
import time
from secrets import token_hex

from pyrogram import ContinuePropagation, StopPropagation, filters
from pyrogram.enums import ButtonStyle, ChatType
from pyrogram.helpers import cell, ikb, table
from pyrogram.types import ForceReply, InputRichMessage

from clients import bot
from database import dB
from logs import logger

MIN_STARS = 50
DRAFT_TTL = 900
DRAFT_KEY = "STARS_ORDER_DRAFT_V1"
LOCKS = tuple(asyncio.Lock() for _ in range(64))

P, S, D = ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER
USERNAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9]")
OPEN_RE = r"^(?:planusers stars|p2star \d+|p2buy st \d+)$"
ACTION_RE = r"^starsdraft:(\d+):([a-f0-9]{12}):(save|cancel)$"


def _lock(user_id):
    return LOCKS[user_id % len(LOCKS)]


def _rupiah(amount):
    return f"Rp{amount:,}".replace(",", ".")


def _price(quantity):
    if quantity < MIN_STARS:
        raise ValueError(f"Minimal pembelian {MIN_STARS} Stars.")
    rate = 286 if quantity <= 500 else 283
    return rate, quantity * rate


def _buttons(draft, confirm=False):
    prefix = f"starsdraft:{draft['buyer']}:{draft['id']}"
    rows = []
    if confirm:
        rows.append([("Simpan Rancangan", f"{prefix}:save", S)])
    rows.append([("Batalkan", f"{prefix}:cancel", D)])
    return ikb(rows)


def _summary_blocks(draft, saved=False):
    return [
        table([
            [cell("PESANAN TELEGRAM STARS", is_header=True),
             cell("MODE PERSIAPAN", is_header=True)],
            [cell("Referensi"), cell(f"STARS-{draft['id'].upper()}")],
            [cell("Tujuan"), cell(f"@{draft['username']}")],
            [cell("Jumlah"), cell(f"{draft['quantity']:,} Stars")],
            [cell("Harga / Stars"), cell(_rupiah(draft["rate"]))],
            [cell("Subtotal"), cell(_rupiah(draft["subtotal"]))],
            [cell("Status"), cell("Rancangan disimpan" if saved else "Belum dibayar")],
        ], bordered=True, striped=True, compact=True),
        table([
            [cell("Belum ada pembayaran atau pengiriman Stars.")],
            [cell("Pengiriman otomatis belum dihubungkan.")],
            [cell("Username baru diperiksa formatnya, belum diverifikasi ke penyedia.")],
        ], bordered=True, compact=True),
    ]


async def _allowed(user_id):
    banned = await dB.get_list_from_var(bot.me.id, "BANNED_USERS") or []
    return user_id not in banned


async def _load(user_id):
    draft = await dB.get_var(user_id, DRAFT_KEY)
    if not isinstance(draft, dict):
        return None
    if time.time() >= draft.get("expires", 0):
        await dB.remove_var(user_id, DRAFT_KEY)
        return None
    return draft


async def _save(draft):
    await dB.set_var(draft["buyer"], DRAFT_KEY, draft)


async def _prompt(client, draft, text):
    prompt = await client.send_message(
        draft["buyer"], text, reply_markup=ForceReply(selective=True),
    )
    draft["prompt_id"] = prompt.id
    await _save(draft)


async def _send_summary(client, draft, saved=False):
    return await client.send_rich_message(
        chat_id=draft["buyer"],
        rich_message=InputRichMessage(blocks=_summary_blocks(draft, saved)),
        reply_markup=None if saved else _buttons(draft, confirm=True),
    )


@bot.on_callback_query(filters.regex(OPEN_RE), group=-60)
async def stars_open(client, query):
    try:
        user_id = query.from_user.id
        if not query.message or query.message.chat.type != ChatType.PRIVATE:
            return await query.answer("Buka layanan ini di chat pribadi bot.", show_alert=True)
        if query.message.chat.id != user_id or not await _allowed(user_id):
            return await query.answer("Akses tidak tersedia.", show_alert=True)
        await query.answer()
        async with _lock(user_id):
            draft = await _load(user_id)
            if draft and draft.get("stage") in {"username", "quantity", "confirm"}:
                return await client.send_message(
                    user_id,
                    "Masih ada rancangan Stars. Lanjutkan atau batalkan dahulu.",
                    reply_markup=_buttons(draft),
                )
            draft = {
                "id": token_hex(6), "buyer": user_id, "stage": "username",
                "created": time.time(), "expires": time.time() + DRAFT_TTL,
            }
            await _save(draft)
            await client.send_rich_message(
                chat_id=user_id,
                rich_message=InputRichMessage(blocks=[
                    table([
                        [cell("BELI TELEGRAM STARS", is_header=True),
                         cell("HARGA", is_header=True)],
                        [cell("50–500 Stars"), cell("Rp286 / Stars")],
                        [cell("501 Stars ke atas"), cell("Rp283 / Stars")],
                        [cell("Minimal pembelian"), cell("50 Stars")],
                    ], bordered=True, striped=True, compact=True),
                    table([
                        [cell("Mode persiapan: belum menerima pembayaran.")],
                    ], bordered=True, compact=True),
                ]),
                reply_markup=_buttons(draft),
            )
            await _prompt(
                client, draft,
                "Masukkan username Telegram tujuan.\n"
                "Boleh tanpa @, contoh: durov.\n"
                "Balas pesan ini. Ketik /cancel untuk batal.",
            )
    except Exception:
        logger.exception("Membuka rancangan Stars gagal")
        if query.message:
            await query.message.reply("Gagal membuka Stars. Coba lagi.")
    finally:
        raise StopPropagation


@bot.on_message(filters.private & filters.text & ~filters.bot, group=-60)
async def stars_input(client, message):
    if not message.from_user:
        raise ContinuePropagation
    user_id = message.from_user.id
    consumed = False
    try:
        async with _lock(user_id):
            draft = await _load(user_id)
            if not draft or draft.get("stage") not in {"username", "quantity", "confirm"}:
                raise ContinuePropagation
            text = message.text.strip()
            if text.casefold() in {"/cancel", "/batal"}:
                consumed = True
                await dB.remove_var(user_id, DRAFT_KEY)
                return await message.reply("Rancangan Stars dibatalkan.")
            if text.startswith("/"):
                await dB.remove_var(user_id, DRAFT_KEY)
                raise ContinuePropagation
            reply = message.reply_to_message
            if not reply or reply.id != draft.get("prompt_id"):
                raise ContinuePropagation
            consumed = True
            if not await _allowed(user_id):
                await dB.remove_var(user_id, DRAFT_KEY)
                return
            if draft["stage"] == "username":
                username = text.removeprefix("@")
                if not USERNAME_RE.fullmatch(username):
                    return await _prompt(
                        client, draft,
                        "Format username tidak valid. Kirim username saja, bukan link.\n"
                        "Contoh: durov\n/cancel untuk batal.",
                    )
                draft.update(username=username, stage="quantity")
                await _prompt(
                    client, draft,
                    f"Tujuan yang kamu tulis: @{username}\n\n"
                    f"Masukkan jumlah Stars, minimal {MIN_STARS}.\n"
                    "Gunakan angka saja, contoh: 50.\n/cancel untuk batal.",
                )
                return
            if draft["stage"] == "quantity":
                if not re.fullmatch(r"[0-9]{1,9}", text):
                    return await _prompt(
                        client, draft,
                        "Kirim jumlah berupa angka saja, tanpa titik atau koma.\n"
                        "Contoh: 50\n/cancel untuk batal.",
                    )
                quantity = int(text)
                if quantity < MIN_STARS:
                    return await _prompt(
                        client, draft,
                        f"Minimal {MIN_STARS} Stars. Masukkan jumlah lagi.\n/cancel untuk batal.",
                    )
                rate, subtotal = _price(quantity)
                draft.update(
                    quantity=quantity, rate=rate, subtotal=subtotal,
                    stage="confirm", expires=time.time() + DRAFT_TTL,
                )
                await _save(draft)
                await _send_summary(client, draft)
                return
            await message.reply("Gunakan tombol pada ringkasan atau /cancel.")
    except ContinuePropagation:
        raise
    except Exception:
        logger.exception("Input rancangan Stars gagal")
        if consumed:
            await message.reply("Input belum berhasil diproses. Coba buka Stars lagi.")
    finally:
        if consumed:
            raise StopPropagation


@bot.on_callback_query(filters.regex(ACTION_RE), group=-60)
async def stars_action(client, query):
    answered = False
    try:
        _, owner, draft_id, action = query.data.split(":")
        user_id = query.from_user.id
        if (
            int(owner) != user_id or not query.message
            or query.message.chat.type != ChatType.PRIVATE
            or query.message.chat.id != user_id
        ):
            return await query.answer("Tombol ini bukan milikmu.", show_alert=True)
        if not await _allowed(user_id):
            return await query.answer("Akses tidak tersedia.", show_alert=True)
        async with _lock(user_id):
            draft = await _load(user_id)
            if not draft or draft.get("id") != draft_id:
                return await query.answer("Rancangan kedaluwarsa. Buka Stars lagi.", show_alert=True)
            if action == "cancel":
                await query.answer("Dibatalkan.")
                answered = True
                await dB.remove_var(user_id, DRAFT_KEY)
                await client.send_message(user_id, "Rancangan Stars dibatalkan.")
            else:
                if draft.get("stage") != "confirm":
                    return await query.answer("Rancangan belum siap atau sudah disimpan.", show_alert=True)
                await query.answer("Menyimpan rancangan...")
                answered = True
                draft.update(stage="saved", saved_at=time.time())
                await _save(draft)
                await _send_summary(client, draft, saved=True)
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
    except Exception:
        logger.exception("Aksi rancangan Stars gagal")
        if answered:
            await client.send_message(query.from_user.id, "Aksi belum selesai. Buka Stars untuk mencoba lagi.")
        else:
            try:
                await query.answer("Terjadi kesalahan. Coba lagi.", show_alert=True)
            except Exception:
                pass
    finally:
        raise StopPropagation