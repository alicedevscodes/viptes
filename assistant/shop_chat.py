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

RESPON = {
    "tidak_tersedia": "Belum bisa dibuka. Coba lagi, ya.",
    "pesanan_hilang": "Pesanannya tidak ditemukan.",
    "bukan_milikmu": "Tombol ini bukan untuk akunmu.",
    "ditutup": "Percakapan untuk pesanan ini sudah selesai.",
    "user": "Nama: {name}\nID: {id}",
    "username": "\nUsername: @{username}",
    "masih_menulis": "Balas pesan yang tadi dulu, ya. Untuk batal, balas dengan /cancel.",
    "penuh": "Sedang ramai. Coba lagi sebentar, ya.",
    "tulis": "<b>Pesanan #{id}</b> · {item}\n<a href='tg://user?id={actor}'>Balas pesan ini</a> untuk mengirim pesan ke {target}.\nKetik /cancel untuk batal.",
    "gagal_buka": "Belum bisa menghubungi admin. Coba lagi sebentar, ya.",
    "jawab_lagi": "Klik Jawab Pesan kalau ingin mengirim pesan lagi.",
    "habis": "Waktunya habis. Klik Jawab Pesan lagi, ya.",
    "batal": "Pesan dibatalkan.",
    "header": "Pesan pembeli untuk pesanan #{id} · {item}",
    "terkirim": "Pesanmu sudah dikirim.",
    "gagal_kirim": "Pesannya belum terkirim. Coba balas pesan tadi lagi, ya.",
}
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
            return await query.answer(RESPON["tidak_tersedia"], show_alert=True)
        async with shop.LOCK:
            order = (await shop.load())["orders"].get(oid)
            if not order or order["kind"] not in shop.CHAT_KINDS:
                return await query.answer(RESPON["pesanan_hilang"], show_alert=True)
            private = query.message.chat.id == order["buyer"]
            authorized = (side == "buyer" and private and actor == order["buyer"]) or (
                side in ("admin", "user") and query.message.chat.id == LOG_SELLER and shop.is_shop_admin(actor)
            )
            if not authorized:
                return await query.answer(RESPON["bukan_milikmu"], show_alert=True)
            if side != "user" and (order.get("chat_closed") or order["state"] not in ("proof", "logged", "delivered", "waiting_owner")):
                return await query.answer(RESPON["ditutup"], show_alert=True)
            snapshot = dict(order)
        if side == "user":
            user = await client.get_users(snapshot["buyer"])
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            info = RESPON["user"].format(name=name, id=user.id)
            if user.username:
                info += RESPON["username"].format(username=user.username)
            return await query.answer(info[:190], show_alert=True)
        async with _PROMPT_LOCK:
            _clean_prompts()
            chat_id = query.message.chat.id
            if any(p["actor"] == actor and p["chat"] == chat_id and not p.get("done") for p in _PROMPTS.values()):
                return await query.answer(RESPON["masih_menulis"], show_alert=True)
            if len(_PROMPTS) >= 256:
                return await query.answer(RESPON["penuh"], show_alert=True)
            await query.answer()
            text = RESPON["tulis"].format(id=oid, item=escape(str(snapshot["name"])), actor=actor, target="admin" if side == "buyer" else "pembeli")
            prompt = await client.send_message(
                chat_id, text, parse_mode=ParseMode.HTML,
                reply_to_message_id=query.message.id, reply_markup=ForceReply(selective=True),
            )
            _PROMPTS[(chat_id, prompt.id)] = {
                "id": oid, "side": side, "actor": actor, "chat": chat_id,
                "expires": time.time() + _TTL, "done": False, "busy": False,
            }
    except Exception:
        logger.exception("Membuka percakapan pesanan gagal")
        try:
            await query.answer(RESPON["gagal_buka"], show_alert=True)
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
            await message.reply(RESPON["jawab_lagi"])
            raise StopPropagation
        if time.time() >= route["expires"]:
            route["done"] = True
            await message.reply(RESPON["habis"])
            raise StopPropagation
        route["busy"] = True
    try:
        async with shop.LOCK:
            order = (await shop.load())["orders"].get(route["id"])
            if not order or order.get("chat_closed") or order["state"] not in ("proof", "logged", "delivered", "waiting_owner"):
                route["done"] = True
                return await message.reply(RESPON["ditutup"])
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
                return await message.reply(RESPON["batal"])
            if route["side"] == "buyer":
                root = order.get("log_message_id")
                if not root:
                    header = await client.send_message(LOG_SELLER, RESPON["header"].format(id=order["id"], item=order["name"]))
                    root = header.id
                await message.copy(LOG_SELLER, reply_to_message_id=root, reply_markup=shop.chat_log_buttons(order))
            else:
                await message.copy(order["buyer"], reply_markup=shop.chat_buyer_buttons(order))
            route["done"] = True
        await message.reply(RESPON["terkirim"], reply_markup=shop.chat_buyer_buttons(order) if route["side"] == "buyer" else None)
    except Exception:
        logger.exception("Pengiriman pesan pesanan gagal")
        await message.reply(RESPON["gagal_kirim"])
    finally:
        route["busy"] = False
        raise StopPropagation
