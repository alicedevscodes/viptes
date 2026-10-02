import asyncio
import os
import random
import sys
import traceback
import httpx
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from pyrogram import filters
from pyrogram.helpers import Button, ikb, RichMessageBuilder
from pyrogram.enums import ButtonStyle
from pyrogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                            KeyboardButton, ReplyKeyboardMarkup,
                            ReplyKeyboardRemove, WebAppInfo)
from pytz import timezone

from clients import bot
from config import AKSES_DEPLOY, CASAKU_LICENSE_KEY, CASAKU_PACKAGE_IDS, LOG_SELLER, OWNER_ID
from database import dB
from helpers import Basic_Effect, ButtonUtils, Emoji, Message, Tools
from logs import logger

last_generated_time = {}


transactions = {}

waktu_jkt = timezone("Asia/Jakarta")


def digit():
    return "".join(random.choice("0123456789") for _ in range(2))

async def casaku_generate(amount: int):
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            "https://api.casaku.id/api/generate/v2/qris",
            headers={"x-license-key": CASAKU_LICENSE_KEY},
            json={
                "qr_id": CASAKU_QRIS_ID,
                "amount": int(amount),
                "useUniqueCode": False,
                "packageIds": CASAKU_PACKAGE_IDS,
                "expiredInMinutes": 10,
                "qrType": "dynamic",
                "paymentMethod": "qris",
                "useQris": True,
            },
        )
    print("CASAKU GENERATE:", r.status_code, r.text)
    r.raise_for_status()
    data = r.json()["data"]
    if not str(data.get("payment_url", "")).startswith("https://"):
        raise ValueError("payment_url kosong/tidak valid")
    return data

async def casaku_status(transaction_id: str):
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            "https://api.casaku.id/api/generate/check-status",
            headers={"x-license-key": CASAKU_LICENSE_KEY},
            json={"transactionId": transaction_id},
        )
    return r.json()["data"]["status"]



async def add_transaction(user_id, month, plan):
    await dB.set_var(user_id, "plan", plan)
    expired = await dB.get_expired_date(user_id)
    if not expired:
        now = datetime.now(waktu_jkt)
        expired = now + relativedelta(months=month)
        await dB.set_expired_date(user_id, expired)


async def user_aggre(client, callback_query):
    await callback_query.answer()
    user_id = callback_query.from_user.id
    del_ = await client.send_message(
        user_id, "<b>Please wait...</b>", reply_markup=ReplyKeyboardRemove()
    )
    await del_.delete()
    await callback_query.message.delete()
    buttons = ButtonUtils.chose_plan()
    return await client.send_message(
        user_id,
        Message.chosePlan(),
        disable_web_page_preview=True,
        reply_markup=buttons,
    )


async def chose_plan(client, callback_query):
    await callback_query.answer()
    await callback_query.message.delete()
    user_id = callback_query.from_user.id
    plan = str(callback_query.data.split()[1])
    PLAN = "Basic" if plan == "basic" else "Pro"
    buttons = ButtonUtils.plus_minus(0, 0, plan)
    return await client.send_message(
        user_id,
        Message.TEXT_PAYMENT(0, 0, 0, PLAN, 0),
        disable_web_page_preview=True,
        reply_markup=buttons,
    )


async def kurang_tambah(client, callback_query):
    QUERY = callback_query.data.split()[0]
    BULAN = int(callback_query.data.split()[1])
    PLAN = str(callback_query.data.split()[3])
    if PLAN == "basic": #vip campuran
        HARGA = 9000
    elif PLAN == "is_pro": #ubot
        HARGA = 9000
    try:
        if QUERY == "kurang":
            if BULAN > 1:
                BULAN -= 1
                TOTAL_HARGA = HARGA
        elif QUERY == "tambah":
            if BULAN < 12:
                BULAN += 1

        HARGA_DASAR = HARGA
        if BULAN >= 12:
            DISKON = 0
        elif BULAN >= 5:
            DISKON = 0
        elif BULAN >= 2:
            DISKON = 0
        else:
            DISKON = 0
        TOTAL_HARGA = HARGA_DASAR - DISKON
        buttons = ButtonUtils.plus_minus(BULAN, TOTAL_HARGA, PLAN)
        PLANNING = "Basic" if PLAN == "basic" else "Pro"
        await callback_query.edit_message_text(
            Message.TEXT_PAYMENT(HARGA, TOTAL_HARGA, BULAN, PLANNING, DISKON),
            disable_web_page_preview=True,
            reply_markup=buttons,
        )
    except Exception:
        pass


async def confirm_pay(client, callback_query):
    await callback_query.answer()
    data = callback_query.data.split()
    month = int(data[1])
    amount = int(data[1])
    plan = str(data[2])
    PLAN = "Basic" if plan == "basic" else "Pro"
    user_id = callback_query.from_user.id
    await callback_query.message.delete()

    if amount == 0:
        return await client.send_message(user_id, "<b>The price cannot be 0.</b>")
    if month == 0:
        return await client.send_message(user_id, "<b>The mont cannot be 0.</b>")
    try:
        if user_id in transactions:
            await callback_query.message.reply(
                "**__📑 You still have a pending transaction.__**",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Cancel", callback_data="batal_payment")]]
                ),
            )
            return

        loading = await callback_query.message.reply(
            "<b><i>Memproses Pembayaran QRIS</i></b>"
        )
        await asyncio.sleep(7)
        await loading.delete()
        await client.send_message(
                   LOG_SELLER,
                   f"""
<b>Someone Has Pay Your Product</b>
""",)
        item_name = f"Sewa Userbot {PLAN} {month} Months"
        base_price = amount
        fee = int(digit())
        total_price = base_price + fee

    try:
        trx = await casaku_generate(total_price)
    except Exception as e:
        logger.error(f"CASAKU GENERATE ERROR: {e}")
        return await client.send_message(user_id, "<b>Gagal membuat QRIS, coba lagi nanti.</b>"
        )
        trx_id = trx["transactionId"]
        qris_url = trx["payment_url"]

        qris_path = f"qris_{user_id}.png"
        Tools.qris_dinamis(str(total_price), qris_path)

        now = datetime.now(waktu_jkt)
        expire_time = now + timedelta(minutes=10)
        formatted_time = expire_time.strftime("%H:%M")
        sent_msg = await callback_query.message.reply_photo(
            qris_path,
            caption=f"""
<b>💳 SCAN QRIS UNTUK MEMBELI SEBLAK</b>
<blockquote><b>
💵 Harga Seblak: `{Message.format_rupiah(base_price)}`
💰 Total Mencret: `{Message.format_rupiah(total_price)}`


⚠️ Setelah melakukanpembayaran kirimkan bukti transfer dibot ini.

<blockquote>© Auto Payment By: @{client.me.username}</blockquote>
""",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📑 Tampilkan Kode QRIS", web_app=WebAppInfo(url=qris_url)
                        )
                    ],
                    [InlineKeyboardButton("❌ Cancel", callback_data="batal_payment")],
                ]
            ),
        )
        
        bukti = await client.ask(
            user_id,
            f'<b>🧾 Silakan kirimkan bukti mencret adna yang sudah Anda buang dicloset</b>',
            filters=filters.photo,
        )
        caption = bukti.caption or ''
        
        try:
            await bukti.copy(
                LOG_SELLER,
                caption=f'\n\nPembayaran: {plan}\nHarga: {Message.format_rupiah(base_price)}',
                reply_markup=ikb(
                        [
                            [
                                ("💎 Akses VIP", f"vip {callback_query.from_user.id} {client.me.username}", ButtonStyle.PRIMARY),
                                ("💻 Akses Ubot", f"ubot {callback_query.from_user.id} {client.me.username} {plan} {month}", ButtonStyle.SUCCESS),
                            ],
                        ]
                    )
                )
            await callback_query.message.reply("<b>✅ Bukti pembayaran sukses dikirim, tunggu sebentar link akan dikirim.</b>")
            await client.send_message(LOG_SELLER, f"Telah membayar di @{client.me.username}")
            if os.path.exists(qris_path):
                os.remove(qris_path)
        except Exception as e:
            print(f"Error saat mengirim bukti pembayaran: {e}")
          
        transactions[user_id] = {
            "qris_path": qris_path,
            "expire_time": expire_time,
            "message_id": sent_msg.id,
            "done": False,
        }

        while True:
            await asyncio.sleep(10)

            if datetime.now(waktu_jkt) > expire_time:
                if user_id in transactions and not transactions[user_id]["done"]:
                    await callback_query.message.reply(
                        "<b><i>Jika admin lama membalas.sabar nunggu njing!.</i></b>"
                    )
                    await client.delete_messages(
                        chat_id=callback_query.message.chat.id,
                        message_ids=transactions[user_id]["message_id"],
                    )
                    del transactions[user_id]
                break
            try:
                status = await casaku_status(trx_id)

                if status == "paid" and not transactions[user_id]["done"]:
                    transactions[user_id]["done"] = True

                    await callback_query.message.reply(
                        "<b><i>Payment received, processing your order...</i></b>"
                    )
                    await client.send_message(
                        LOG_SELLER,
                        f"""
<b>📝「 Payment Successfully 」</b>

<blockquote><b><i>👤 User Name: `{callback_query.from_user.first_name}`
🆔 User ID: `{str(callback_query.from_user.id)[:3]}######`
📦 Item: `{item_name}`
💵 Price: `{Message.format_rupiah(base_price)}`
📅 Date: `{now.strftime('%d-%m-%Y')}`
⏰ Time: `{now.strftime('%H:%M')}`</i></b></blockquote>

<blockquote>© Auto Payment @{client.me.username}</blockquote>
""",
                    )
                    await client.delete_messages(
                        chat_id=callback_query.message.chat.id,
                        message_ids=transactions[user_id]["message_id"],
                    )
                    del transactions[user_id]

                    await add_transaction(user_id, month, plan)
                    if user_id not in AKSES_DEPLOY:
                        AKSES_DEPLOY.append(user_id)
                    await client.send_message(
                        user_id,
                        "<b><i>✅ Payment successful.\nClick the button below to create your UserBot.</i></b>",
                        reply_markup=ReplyKeyboardMarkup(
                            [[KeyboardButton("✨ Mulai Buat Userbot")]],
                            resize_keyboard=True,
                            one_time_keyboard=True,
                        ),
                    )
                    break

            except Exception as e:
                print(f"Error checking payment: {e}")

    except Exception as er:
        logger.error(f"ERROR: {traceback.format_exc()}")
        logger.error(f"ERROR: {sys.exc_info()[-1].tb_lineno}")
        return await client.send_message(
            user_id, "<b>An error occurred, please try again.</b>"
        )


async def kasih_vip(client, callback_query):
    user_ids = int(callback_query.data.split()[1])
    bot_user = callback_query.data.split()[2]
    msg = f"""<b>✅ Pembelian Channel VIP Sukses</b>
    
Link VIP: <spoiler>cari dipencarian: @satorugojovip | satorugojovip.t.me | t.me/satorugojovip</spoiler>
Cara melihat medianya:
Klik profile channel diatas, lalu akan terlihat semua media.
Atau bisa klik pin pesan yang sudah tersemat
<blockquote><b>Jangan lupa beli userbot dengan fitur curi foto & video sekali liat
Untuk penjelasan detailnya silahkan klik tombol Contoh Kelebihan Userbot</b></blockquote>
✨ Selamat menikmat"""

    buttons = ikb(
        [
            [
                (
                    (("💻 Beli Userbot"), f"https://t.me/devfavbot?start=kontol", "url", ButtonStyle.PRIMARY),
                    (("✨ Kelebihan Userbot"), f"https://t.me/devspaybot?start=kontol", "url", ButtonStyle.SUCCESS),
                ),
            ],
        ]
    )
    await client.send_message(
        user_ids,
        msg,
        reply_markup=buttons,
        effect_id=5104841245755180586,
  )
    await callback_query.message.edit("**✅ Pesan telah di kirim**")

  
async def kasih_ubot(client, callback_query):
    await callback_query.answer()
    data = callback_query.data.split()
    user_ids = int(data[1])     # ID PEMBELI, ini yang benar dipakai untuk semua proses di bawah
    bot_user = data[2]
    plan = str(data[3])
    month = int(data[4])
    PLAN = "Basic" if plan == "basic" else "Pro"

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

async def cancel_payment(client, callback_query):
    user_id = callback_query.from_user.id
    await callback_query.answer()

    if user_id in transactions:
        qris_path = transactions[user_id]["qris_path"]

        if os.path.exists(qris_path):
            os.remove(qris_path)

        try:
            await client.delete_messages(
                chat_id=callback_query.message.chat.id,
                message_ids=transactions[user_id]["message_id"],
            )
        except Exception:
            pass

        del transactions[user_id]

        await callback_query.message.reply(
            "**__📑 Transaksi Berhasil Dibatalkan.__**",
            reply_markup=ButtonUtils.start_menu(user_id),
        )
    else:
        await callback_query.message.reply("**__❌ Tidak Ada Transaksi Yang Aktif__**")


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

    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply(
                f"{em.gagal}**Incorrect format. Use:** <code>.pay amount, description</code>"
            )
        try:
            amount_str, description = args[1].split(",", maxsplit=1)
            amount = int(amount_str.strip())
            description = description.strip()
        except ValueError:
            return await message.reply(
                f"{em.gagal}**Incorrect format. Use:** <code>.pay amount, description</code>"
            )

        loading = await message.reply(f"{em.proses}**Prosesing..**")
        await asyncio.sleep(2)
        await loading.delete()

        fee = int(digit())
        total_amount = amount + fee

        now_wib = datetime.now(waktu_jkt)
        expire_time_wib = now_wib + timedelta(minutes=10)
        formatted_time = expire_time_wib.strftime("%H:%M")

        time_suffix = now_wib.strftime("%H%M%S")
        qris_path = f"qris_{user_id}_{time_suffix}.png"
        Tools.qris_dinamis(str(total_amount), qris_path)

        sent_message = await message.reply_photo(
            qris_path,
            caption=(
                f"""
<b>📃「 Waiting Payment 」</b>

<blockquote><b><i>{em.profil}Item: `{description}`
{em.net}Price: `Rp{amount:,}`
{em.speed}Total Payment: `Rp{total_amount:,}`
{em.warn}Expiration Time: `{formatted_time}`

Please scan the QRIS above to complete the payment.
If you encounter any issues, contact <a href='tg://user?id={OWNER_ID}'>ADMIN</a>
Type `.cancelpay` to cancel the transaction.</i></b></blockquote>

<blockquote>© Auto Payment @{bot.me.username}</blockquote>
"""
            ),
        )

        if os.path.exists(qris_path):
            os.remove(qris_path)

        transactions[user_id] = {
            "qris_path": qris_path,
            "expire_time": expire_time_wib,
            "message_id": sent_message.id,
            "description": description,
            "amount": amount,
            "total_amount": total_amount,
            "paid": False,
        }

        while True:
            await asyncio.sleep(10)

            if datetime.now(waktu_jkt) > expire_time_wib:
                if user_id in transactions:
                    await message.reply(
                        f"{em.gagal}**Transaction canceled due to expiration.**"
                    )
                    if os.path.exists(qris_path):
                        os.remove(qris_path)
                    await client.delete_messages(
                        chat_id=message.chat.id,
                        message_ids=transactions[user_id]["message_id"],
                    )
                    del transactions[user_id]
                break

            try:
                response = await Tools.fetch.get(
                    f"https://casaku.com/api/mutasi/qris/{MERCHANTID}/{APIKEY_CASA}"
                )
                result = response.json().post("data", [])
                if result and not transactions[user_id]["paid"]:
                    for transaction in result:
                        if int(transaction["amount"]) == total_amount:
                            transactions[user_id]["paid"] = True

                            await message.reply(
                                f"""
<blockquote><b><i>{em.sukses}Payment received successfully!

{em.profil}Item: `{description}`
{em.net}Price: `Rp{amount:,}`
{em.speed}Total Paid: `Rp{total_amount:,}`</i></b></blockquote>
"""
                            )
                            if os.path.exists(qris_path):
                                os.remove(qris_path)
                            await client.delete_messages(
                                chat_id=message.chat.id,
                                message_ids=transactions[user_id]["message_id"],
                            )
                            del transactions[user_id]
                            return

            except Exception as e:
                print(f"Error while checking payment: {e}")

    except ValueError:
        return await message.reply(
            f"{em.gagal}**Invalid amount. Make sure it is a number.**"
        )


async def cancelpay_cmd(client, message):
    em = Emoji(client)
    await em.get()

    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return await message.reply(
            f"{em.gagal}**Sorry, this feature is only for the Owner.**"
        )

    if user_id in transactions:
        if os.path.exists(transactions[user_id]["qris_path"]):
            os.remove(transactions[user_id]["qris_path"])

        await client.delete_messages(
            chat_id=message.chat.id, message_ids=transactions[user_id]["message_id"]
        )
        del transactions[user_id]

        return await message.reply(
            f"{em.sukses}**Transaction has been successfully canceled.**"
        )
    else:
        return await message.reply(
            f"{em.warn}**There is no active transaction to cancel.**"
        )
