from datetime import datetime
from time import time

from pyrogram import enums
from pyrogram.errors import ChannelPrivate
from pyrogram.helpers import kb
from pyrogram.raw.functions import Ping
from pyrogram.types import ReplyKeyboardRemove
from pytz import timezone

from clients import navy
from config import BOT_NAME, SUDO_OWNERS
from database import dB
from helpers import Emoji, TokenReferal, get_time, start_time
from logs import logger


async def mestats_cmd(client, message):
    em = Emoji(client)
    await em.get()
    pong_, uptime_, owner_, ubot_, proses_, sukses_ = await em.get_costum_text()
    proses = await message.reply_text(f"{em.proses}**{proses_}**")
    start = datetime.now()
    zz = 0
    nanki = 0
    luci = 0
    tgr = 0
    ceger = 0
    kntl = 0
    benet = 0
    dimari = set()
    try:
        async for dialog in client.get_dialogs():
            try:
                if dialog.chat.type == enums.ChatType.PRIVATE:
                    zz += 1
                elif dialog.chat.type == enums.ChatType.BOT:
                    ceger += 1
                elif dialog.chat.type == enums.ChatType.GROUP:
                    nanki += 1
                elif dialog.chat.type == enums.ChatType.SUPERGROUP:
                    luci += 1
                    user_s = await dialog.chat.get_member(client.me.id)
                    if user_s.status in (
                        enums.ChatMemberStatus.OWNER,
                        enums.ChatMemberStatus.ADMINISTRATOR,
                    ):
                        kntl += 1
                elif dialog.chat.type == enums.ChatType.CHANNEL:
                    tgr += 1
            except ChannelPrivate:
                benet += 1
                dimari.add(dialog.chat.id)
                await client.leave_chat(dialog.chat.id)
                logger.info(f"Left chat: {dialog.chat.id}")
                continue
    except ChannelPrivate:
        benet += 1
        dimari.add(dialog.chat.id)

    end = datetime.now()
    ms = (end - start).seconds
    if not dimari:
        dimari = None
    await proses.delete()
    return await message.reply_text(
        """
>{} **Succesful extract your data in `{}` seconds
>`{}` Private Messages.
>`{}` Groups.
>`{}` Super Groups.
>`{}` Channels.
>`{}` Admin in Chats.
>`{}` Bots.
>`{}` Group With Trouble
>
>I've trouble with this chat : 
>- `{}`**""".format(
            em.sukses,
            ms,
            zz,
            nanki,
            luci,
            tgr,
            kntl,
            ceger,
            benet,
            dimari,
        )
    )


async def close_kb(client, message):
    return await message.reply_text(
        "<b>Keyboard Ditutup</b>", reply_markup=ReplyKeyboardRemove()
    )


async def cek_status_akun(client, message):
    tokenref = await TokenReferal.create()
    user_id = message.from_user.id
    seles = await dB.get_list_from_var(client.me.id, "SELLER")
    if user_id not in navy._get_my_id:
        status2 = "tidak aktif"
    else:
        status2 = "aktif"
    if user_id in SUDO_OWNERS:
        status = "<b>[Admins]</b>"
    elif user_id in seles:
        status = "<b>[Seller]</b>"
    else:
        status = "<b>[Costumer]</b>"
    uptime = await get_time((time() - start_time))
    await client.invoke(Ping(ping_id=0))
    exp = await dB.get_expired_date(user_id)
    if str(message.from_user.id) not in tokenref.users:
        Referral = await tokenref.generate_referral_code(str(message.from_user.id))
    else:
        getref = tokenref.users[str(message.from_user.id)]
        Referral = getref.get("referral_code")
    status_referal = await tokenref.get_referral_stats(str(user_id))
    habis = (
        exp.astimezone(timezone("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M")
        if exp
        else "None"
    )
    prefix = client.get_prefix(user_id)
    plan = await dB.get_var(user_id, "plan")
    is_pro = "Pro" if plan == "is_pro" else "Basic"
    keyboard = kb([["↩️ Beranda"]], resize_keyboard=True, one_time_keyboard=True)
    return await message.reply(
        f"""
<blockquote>
<b>{BOT_NAME}</b>
    <b>Status Ubot:</b> <code>{status2}</code>
      <b>Status Pengguna:</b> <i>{status}</i>
      <b>Plan:</b> <b>{is_pro}</b>
      <b>Prefixes :</b> <code>{' '.join(prefix)}</code>
      <b>Tanggal Kedaluwarsa:</b> <code>{habis}</code>
      <b>Uptime Ubot:</b> <code>{uptime}</code>
      <b>Token:</b> <code>{status_referal['token']}</code>
      <b>Kode Referral:</b> <code>{Referral}</code>
      <b>Pengguna Referral:</b> <code>{status_referal['invited_users_count']}</code>
</blockquote>
""",
        reply_markup=keyboard,
    )
