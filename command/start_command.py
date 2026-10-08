import asyncio
import random

from pyrogram import enums
from pyrogram.helpers import (
    Button,
    RichMessageBuilder,
    heading,
    paragraph,
    details,
    divider,
    code_block,
    math_expression,
    details,
    pull_quote,
    cell,
    table,
    send_rich,
    photo_block,
    video_block,
    send_markdown_rich,
)
from pyrogram.types import InputRichMessage, RichTextMarked, RichTextTextMention, RichTextBold, RichTextCustomEmoji
from clients import bot
from config import KYNAN, LOG_SELLER, SUDO_OWNERS, BOT_NAME
from database import dB, state
from helpers import Basic_Effect, ButtonUtils, Message, Tools, no_commands, emos
from logs import logger


def emo(emoji_id, alt="✨"):
    return RichTextCustomEmoji(custom_emoji_id=str(emoji_id), alternative_text=alt)


async def gen_image(client):
    image = None
    file_id = await dB.get_var(client.me.id, "IMAGE_START")
    if file_id:
        image = {"photo": file_id} if file_id.startswith("AgAC") else {"video": file_id}
        return image
    return None


async def setimg_start(client, message):
    user = message.from_user if message.from_user else message.sender_chat
    if user.id not in KYNAN:
        return
    if message.reply_to_message:
        proses = await message.reply("<blockquote>**Tunggu sebentar..**</blockquote>")
        reply = message.reply_to_message
        if not reply.media:
            return await proses.edit(
                "<blockquote>**Silahkan balas ke pesan foto atau video**</blockquote>"
            )
        file_id = Tools.get_file_id(reply).get("file_id")
        await dB.set_var(client.me.id, "IMAGE_START", file_id)
        return await proses.edit(
            f"<blockquote>**Berhasil mengatur media start ke: <a href='{reply.link}'>pesan ini</a>**</blockquote>",
            disable_web_page_preview=True,
        )
    else:
        if len(message.command) == 2:
            args = message.command[1]
            if args in ["off", "disable"]:
                await dB.remove_var(client.me.id, "IMAGE_START")
                return await message.reply(
                    "<blockquote>**Media start dinon-aktifkan**</blockquote>"
                )
            else:
                return await message.reply(
                    "<blockquote>**Silahkan balas ke media jika ingin mengatur pesan start media, atau ketik `/setimg off` untuk menon-aktifkan pesan media start.**</blockquote>"
                )
        else:
            return await message.reply(
                "<blockquote>**Silahkan balas ke media jika ingin mengatur pesan start media, atau ketik `/setimg off` untuk menon-aktifkan pesan media start.**</blockquote>"
            )


async def setads_bot(client, message):
    user = message.from_user if message.from_user else message.sender_chat
    if user.id not in KYNAN:
        return
    if not message.reply_to_message:
        return await message.reply("**Silahkan balas ke teks**")
    proses = await message.reply("**Tunggu sebentar..**")
    reply = message.reply_to_message
    text = reply.text or reply.caption or ""
    await dB.set_var(client.me.id, "ads", text)
    return await proses.edit(
        f"**Pesan ads berhasil diatur ke: <a href='{reply.link}'>pesan ini</a>**"
    )


def _format_user_mention(user):
    """user = objek pyrogram.types.User asli (mis. message.from_user).
    Return RichTextTextMention supaya mention jadi link aktif, bukan teks HTML mentah."""
    full_name = f"{user.first_name} {user.last_name or ''}".strip()
    return RichTextTextMention(text=full_name, user=user)


async def welcome_rich_table(
    client,
    message,
    reply_markup=None,
    effect_id=None,
    **_diabaikan,  # tampung kwargs yang tidak didukung send_rich_message
):
    user_mention = _format_user_mention(message.from_user)
    rich = InputRichMessage(
        blocks=[
            paragraph([emo(5967683261940372267), " Hi\n", user_mention]),
            paragraph([
                emo(5215420556089776398, "🤖"),
                f" Ini adalah contoh bot auto payment"
            ]),
            divider(),
            table(
              [
                  [
                      cell(
                          [
                              emo(6269368817147711866, "💎"),
                              RichTextBold(" DAGANGAN LOE"),
                          ],
                          is_header=True,
                      )
                  ],
                  [
                      cell(
                          [
                              emo(5264946326491134516, "🎮"),
                              " Seblak Mencret",
                          ]
                      )
                  ],
                  [
                      cell(
                          [
                              emo(5789632781344575552, "✅"),
                              " Mixue Mencret",
                          ]
                      )
                  ],
                  [
                      cell(
                          [
                              emo(5935835460965242201, "✅"),
                              " Mie Ayam Mencret",
                          ]
                      )
                  ],
                  [
                      cell(
                          [
                              emo(6122810011723761490, "✨"),
                              " ",
                              emo(6156658206601906188, "✨"),
                              " ",
                              emo(6122839423659804332, "✨"),
                              " ",
                              emo(6123119356743256249, "✨"),
                              " ",
                              emo(6122857737400354779, "✨"),
                              " E-Wallet",
                          ]
                      )
                  ],
                  [
                      cell(
                          [
                              emo(6124968881330064561, "✨"),
                              " ",
                              emo(6127403058340038849, "✨"),
                              " ",
                              emo(6127616621293865541, "✨"),
                              " ",
                              emo(6125174374040340808, "✨"),
                              " ",
                              emo(6127693200560753259, "✨"),
                              " Bank",
                          ]
                      )
                  ],
              ],
          ),
            divider(),
            details(
                [emo(5431420628978641216, "🤖"), " Misal penjelasan dagangan loe"],
                paragraph([
                    emo(5373052667671093676, "🤖"),
                    " Ini adalah penjelasan dagangan loe yang bikin mencret mencret "
                ]),
            ),
            table(
                [
                    [cell(["AliceDevs Core v3.14 ", emo(5456140674028019486, "⚡")], align="center")],
                ],
            ),
            divider(),
        ]
    )

    return await client.send_rich_message(
        chat_id=message.chat.id,
        rich_message=rich,
        reply_markup=reply_markup,
        effect_id=effect_id,
    )


async def start_home(client, message):
    if message.chat.type != enums.ChatType.PRIVATE:
        return
    broadcast = await dB.get_list_from_var(client.me.id, "BROADCAST")
    user = message.from_user
    if user.id not in broadcast:
        await dB.add_to_var(client.me.id, "BROADCAST", user.id)
    image_start = await gen_image(client)
    if message.from_user.id in SUDO_OWNERS:
        buttons = ButtonUtils.start_menu(is_admin=True)
    else:
        buttons = ButtonUtils.start_menu(is_admin=False)
        sender_id = message.from_user.id
        sender_mention = message.from_user.mention
        sender_name = message.from_user.first_name

        await client.send_message(
            LOG_SELLER,
            f"<b>User: {sender_mention}\nID: `{sender_id}`\nName: {sender_name}\nHas started your bot.</b>",
        )

    if image_start:
        if "video" in image_start:
            loading = await message.reply_sticker(
                "CAACAgUAAyEFAAToxR-FAAIEvWrCDM4isV-eCFKPaMtlQ4hQkQrRAALGAQACZWvpVO9gdZa9gYmkHgQ"
            )
            await asyncio.sleep(1)
            await loading.delete()
            await message.reply_video(
                video=image_start["video"],
                reply_markup=buttons,
                effect_id=5104841245755180586,
            )
        elif "photo" in image_start:
            loading = await message.reply_sticker(
                "CAACAgUAAyEFAAToxR-FAAIEvWrCDM4isV-eCFKPaMtlQ4hQkQrRAALGAQACZWvpVO9gdZa9gYmkHgQ"
            )
            await asyncio.sleep(1)
            await loading.delete()
            await message.reply_photo(
                photo=image_start["photo"],
                reply_markup=buttons,
                effect_id=5104841245755180586,
            )
    else:
        loading = await message.reply_sticker(
            "CAACAgUAAyEFAAToxR-FAAIEvWrCDM4isV-eCFKPaMtlQ4hQkQrRAALGAQACZWvpVO9gdZa9gYmkHgQ"
        )
        await asyncio.sleep(1)
        await loading.delete()
        return await welcome_rich_table(
            client,
            message,
            reply_markup=buttons,
            effect_id=5104841245755180586,
        )


async def button_bot(client, message):
    link = message.text.split(None, 1)[1]
    tujuan, _id = Tools.extract_ids_from_link(link)
    txt = state.get(message.from_user.id, "edit_reply_markup")
    teks, button_kbd = ButtonUtils.parse_msg_buttons(txt)
    if button_kbd:
        button_kbd = await ButtonUtils.create_inline_keyboard(button_kbd)
    return await client.edit_message_reply_markup(
        chat_id=tujuan, message_id=_id, reply_markup=button_kbd
    )


async def getid_bot(client, message):
    if len(message.command) < 2:
        return
    query = message.text.split()[1]
    try:
        reply = message.reply_to_message
        media = Tools.get_file_id(reply)
        data = {"file_id": media["file_id"], "type": media["message_type"]}
        state.set(message.from_user.id, query, data)
        return
    except Exception as er:
        logger.error(f"{str(er)}")


async def request_bot(client, message):
    user_id = message.from_user.id
    if not message.reply_to_message:
        reply_text = (
            "<b>English:</b> Please use the /request command by replying to a text message or media with a caption. And explain the features you want in detail to make it easier for the admin.\n\n"
            "<b>Indonesia:</b> Silahkan gunakan perintah /request dengan cara membalas pesan teks atau media dengan caption. Serta jelaskan fitur yang anda inginkan dengan detail agar memudahkan admin."
        )
        return await message.reply(reply_text)

    forward = await client.forward_messages(
        chat_id=LOG_SELLER,
        from_chat_id=message.chat.id,
        message_ids=message.reply_to_message.id,
    )
    await dB.set_var(forward.id, f"REQUEST_{forward.id}", user_id)
    return await message.reply(
        "<b>English:</b> Your report has been successfully submitted. Please wait for a response from the admin.\n\n"
        "<b>Indonesia:</b> Laporan kamu berhasil dikirimkan. Silahkan tunggu jawaban dari admin."
    )


async def lapor_bug(client, message):
    if client.me.id != bot.id:
        return
    user_id = message.from_user.id
    if not message.reply_to_message:
        reply_text = (
            "<b>Cara Kirim:\nKirim Screenshot Transaksi pembelian userbot dibot ini,\nSertakan caption `Plan Basic/Pro`\nLalu reply bukti dengan perintah /bukti.</b>"
        )
        return await message.reply(reply_text)
    forward = await client.forward_messages(
        chat_id=LOG_SELLER,
        from_chat_id=message.chat.id,
        message_ids=message.reply_to_message.id,
    )
    await dB.set_var(forward.id, f"BUG_{forward.id}", user_id)

    return await message.reply(
        "<b>✅ Bukti sukses dikirim ke admin, tunggu admin memberi akses userbot</b>."
    )


async def incoming_message(client, message):
    if message.chat.type != enums.ChatType.PRIVATE:
        return
    if message.sticker:
        return
    text = message.text or message.caption or ""
    if (
        text
        and text.startswith("/")
        or text in no_commands
        or not text.startswith("#bukti")
    ):
        return
    user_id = message.from_user.id
    forward = await client.forward_messages(
        chat_id=LOG_SELLER, from_chat_id=message.chat.id, message_ids=message.id
    )
    await dB.set_var(forward.id, f"FORWARD_{forward.id}", user_id)


async def outgoing_reply(client, message):
    rep = message.reply_to_message
    if not rep:
        return
    for prefix in ("REQUEST_", "BUG_", "FORWARD_"):
        user_id = await dB.get_var(rep.id, f"{prefix}{rep.id}")
        if user_id:
            return await client.copy_message(
                chat_id=user_id, from_chat_id=message.chat.id, message_id=message.id
            )