from pyrogram import ContinuePropagation, StopPropagation, filters
from clients import bot
from config import OWNER_ID
from helpers import manual_shop as shop
from command import payment_command as pay
from command import pay_peller as extra


@bot.on_callback_query(filters.regex(r"^(?:buynokos |p2buy |shopdone:|batal_payment$|planusers suntik$)"), group=-30)
async def checkout_callback(client, query):
    try:
        data = query.data.split()
        if query.data.startswith("shopdone:"):
            return await shop.finish(query)
        if query.data == "batal_payment":
            async with shop.LOCK:
                order = shop.active(await shop.load(), query.from_user.id)
                if not order:
                    raise ContinuePropagation
                if order["state"] != "awaiting_photo":
                    return await query.answer("Bukti sudah diterima. Hubungi owner untuk pembatalan/refund.", show_alert=True)
                await shop.cancel(order)
            return await query.answer("Pesanan dibatalkan.", show_alert=True)
        if data[0] == "buynokos" and len(data) == 2:
            return await shop.checkout(client, query, "nk", data[1])
        if data[0] == "p2buy" and len(data) == 3:
            return await shop.checkout(client, query, data[1], data[2])
        if query.data == "planusers suntik":
            return await shop.checkout(client, query, "gc", "manual")
    except ContinuePropagation:
        raise
    finally:
        if query.data != "batal_payment" or 'order' in locals() and order:
            raise StopPropagation


@bot.on_message(filters.private & filters.photo & ~filters.bot, group=-30)
async def proof_photo(client, message):
    if await shop.accept_photo(message):
        raise StopPropagation
    raise ContinuePropagation


@bot.on_message(filters.private & filters.user(OWNER_ID) & filters.command("bindnokos"), group=-30)
async def bind_nokos(client, message):
    try:
        await shop.bind(message)
    except Exception as error:
        await message.reply(f"Bind gagal: {type(error).__name__}. Periksa format dan userbot stok; session tidak ditampilkan.")
    raise StopPropagation


@bot.on_message(filters.private & filters.command("pesananku"), group=-30)
async def my_order(client, message):
    async with shop.LOCK:
        book = await shop.load()
        orders = [o for o in book["orders"].values() if o["buyer"] == message.from_user.id]
        order = orders[-1] if orders else None
        text = f"Pesanan #{order['id']}\nItem: {order['name']}\nStatus: {order['state']}" if order else "Belum ada pesanan."
    await message.reply(text)
    raise StopPropagation


@bot.on_message(filters.user(OWNER_ID) & filters.command(["addnf", "delnf", "addnokos", "del"]), group=-30)
async def stock_mutation(client, message):
    async with shop.LOCK:
        book = await shop.load()
        for order in book["orders"].values():
            if order["state"] in ("awaiting_photo", "proof", "logged"):
                if order["kind"] == "nk":
                    pay.reserved_nokos[order["stock"]] = order["buyer"]
                elif order["kind"] == "nf":
                    extra.nf_reserved[order["stock"]] = order["buyer"]
        cmd = message.command[0].lower()
        if cmd in ("addnf", "delnf"):
            if cmd == "delnf" and any(value in extra.nf_reserved for value in message.text.split()[1:]):
                await message.reply("Akun sedang dipesan; tidak boleh dihapus.")
            else:
                await extra.nf_cmd(client, message)
        elif cmd == "addnokos":
            await pay.tambah_nokos_cmd(client, message)
        else:
            await pay.hapus_nokos_cmd(client, message)
    raise StopPropagation


shop.start_worker()


@bot.on_callback_query(filters.regex(r"^(?:p2nf |p2done |nokos )"), group=-31)
async def protect_legacy_stock(client, query):
    if query.from_user.id != OWNER_ID:
        await query.answer("Akses owner saja.", show_alert=True)
        raise StopPropagation
    raise ContinuePropagation
