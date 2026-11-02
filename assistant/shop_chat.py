import asyncio
import time
from html import escape

from pyrogram import ContinuePropagation, StopPropagation, filters
from pyrogram.enums import ParseMode
from pyrogram.types import ForceReply
from clients import bot
from config import LOG_SELLER
from database import dB
from helpers import manual_shop as shop
from logs import logger

_PROMPTS = {}
_PROMPT_LOCK = asyncio.Lock()
_TTL = 300


def _clean_prompts():
    for key, value in tuple(_PROMPTS.items()):
        if time.time() >= value["expires"]:
            _PROMPTS.pop(key, None)


@bot.on_callback_query(filters.regex(r"^shopchat:(?:buyer|admin|user):[a-f0-9]{12}$"), group=-33)
async def order_chat_callback(client, query):
    try:
        _, side, oid = query.data.split(":")
        actor = query.from_user.id
        banned = await dB.get_list_from_var(client.me.id, "BANNED_USERS") or []
        if actor in banned or not query.message:
            return await query.answer("Akses tidak tersedia.", show_alert=True)
        async with shop.LOCK:
            order = (await shop.load())["orders"].get(oid)
            if not order or order["kind"] not in shop.CHAT_KINDS:
                return await query.answer("Pesanan tidak ditemukan.", show_alert=True)
            private = query.message.chat.id == order["buyer"]
            authorized = (side == "buyer" and private and actor == order["buyer"]) or (
                side in ("admin", "user") and query.message.chat.id == LOG_SELLER and shop.is_shop_admin(actor)
            )
            if not authorized:
                return await query.answer("Tombol ini bukan untukmu.", show_alert=True)
            if side != "user" and (order.get("chat_closed") or order["state"] not in ("proof", "logged", "delivered", "waiting_owner")):
                return await query.answer("Percakapan pesanan sudah ditutup atau belum tersedia.", show_alert=True)
            snapshot = dict(order)
        if side == "user":
            user = await client.get_users(snapshot["buyer"])
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            info = f"User: {name}\nID: {user.id}" + (f"\nUsername: @{user.username}" if user.username else "")
            return await query.answer(info[:190], show_alert=True)
        async with _PROMPT_LOCK:
            _clean_prompts()
            chat_id = query.message.chat.id
            if any(p["actor"] == actor and p["chat"] == chat_id and not p.get("done") for p in _PROMPTS.values()):
                return await query.answer("Masih ada prompt pesan aktif. Balas prompt itu atau kirim /cancel sebagai reply.", show_alert=True)
            if len(_PROMPTS) >= 256:
                return await query.answer("Sesi percakapan sedang penuh. Coba lagi nanti.", show_alert=True)
            await query.answer()
            text = (
                f"<b>Pesanan #{oid}</b> · {escape(str(snapshot['name']))}\n"
                f"<a href='tg://user?id={actor}'>Balas pesan ini</a> dengan pesan untuk "
                f"{'admin' if side == 'buyer' else 'buyer'}.\n"
                "Sesi berlaku 5 menit. Reply /cancel untuk membatalkan."
            )
            prompt = await client.send_message(chat_id, text, parse_mode=ParseMode.HTML,
                                              reply_to_message_id=query.message.id,
                                              reply_markup=ForceReply(selective=True))
            _PROMPTS[(chat_id, prompt.id)] = {
                "id": oid, "side": side, "actor": actor, "chat": chat_id,
                "expires": time.time() + _TTL, "done": False, "busy": False,
            }
    except Exception:
        logger.exception("Membuka percakapan pesanan gagal")
        try:
            await query.answer("Percakapan gagal dibuka. Coba lagi.", show_alert=True)
        except Exception:
            pass
    finally:
        raise StopPropagation


@bot.on_message(filters.reply & ~filters.bot & (filters.private | filters.chat(LOG_SELLER)), group=-45)
async def order_chat_reply(client, message):
    key = (message.chat.id, message.reply_to_message.id)
    async with _PROMPT_LOCK:
        route = _PROMPTS.get(key)
        if not route:
            raise ContinuePropagation
        actor = message.from_user.id if message.from_user else None
        if actor != route["actor"]:
            raise StopPropagation
        if route.get("busy") or route.get("done"):
            await message.reply("Gunakan tombol Jawab Pesan untuk membuka sesi baru.")
            raise StopPropagation
        if time.time() >= route["expires"]:
            route["done"] = True
            await message.reply("Sesi berakhir. Tekan Jawab Pesan kembali.")
            raise StopPropagation
        route["busy"] = True
    try:
        async with shop.LOCK:
            order = (await shop.load())["orders"].get(route["id"])
            if not order or order.get("chat_closed") or order["state"] not in ("proof", "logged", "delivered", "waiting_owner"):
                route["done"] = True
                return await message.reply("Percakapan pesanan sudah ditutup.")
            banned = await dB.get_list_from_var(client.me.id, "BANNED_USERS") or []
            if actor in banned:
                route["done"] = True
                return
            if route["side"] == "buyer" and actor != order["buyer"]:
                route["done"] = True
                return
            if route["side"] == "admin" and not shop.is_shop_admin(actor):
                route["done"] = True
                return
            text = (message.text or "").strip().casefold()
            if text in {"/cancel", "cancel", "/batal", "batal"}:
                route["done"] = True
                return await message.reply("Pengiriman pesan dibatalkan.")
            if route["side"] == "buyer":
                root = order.get("log_message_id")
                if not root:
                    header = await client.send_message(LOG_SELLER, f"Pesan buyer untuk pesanan #{order['id']} · {order['name']}")
                    root = header.id
                await message.copy(LOG_SELLER, reply_to_message_id=root, reply_markup=shop.chat_log_buttons(order))
            else:
                await message.copy(order["buyer"], reply_markup=shop.chat_buyer_buttons(order))
            route["done"] = True
        await message.reply("Pesan berhasil dikirim.", reply_markup=shop.chat_buyer_buttons(order) if route["side"] == "buyer" else None)
    except Exception:
        logger.exception("Pengiriman pesan pesanan gagal")
        await message.reply("Pesan belum berhasil dikirim. Coba balas prompt yang sama kembali.")
    finally:
        route["busy"] = False
        raise StopPropagation
