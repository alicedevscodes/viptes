import asyncio
import traceback
from uuid import uuid4

from pyrogram.enums import ParseMode

from clients import bot
from database import dB, state
from helpers import ButtonUtils, Emoji, Message, Tools, animate_proses
from logs import logger


async def savenote_cmd(client, message):
    em = Emoji(client)
    await em.get()

    xx = await animate_proses(message, em.proses)
    rep = message.reply_to_message
    if len(message.command) < 2 or not rep:
        return await xx.edit(f"{em.gagal}**Please reply message and give note name**")
    nama = message.text.split()[1]
    getnotes = await dB.get_var(client.me.id, nama, "notes")
    if getnotes:
        return await xx.edit(f"{em.gagal}**Note {nama} already exist!**")
    value = None

    text = rep.text or rep.caption or ""
    entities = rep.entities or rep.caption_entities
    if rep.media:
        copy = await rep.copy(bot.me.username)
        sent = await client.send_message(
            bot.me.username, f"/id {nama}", reply_to_message_id=copy.id
        )
        await asyncio.sleep(1)
        await sent.delete()
        await copy.delete()
        extract = Tools.dump_entity(text, entities)
        type = state.get(client.me.id, nama)
        value = {
            "type": type["type"],
            "file_id": type["file_id"],
            "result": extract,
        }
    else:
        extract = Tools.dump_entity(text, entities)
        value = {"type": "text", "file_id": "", "result": extract}
    if value:
        await dB.set_var(client.me.id, nama, value, "notes")
        return await xx.edit(f"{em.sukses}**Saved {nama} note!!**")
    else:
        return await xx.edit(f"{em.gagal}**Please reply message and give note name**")


async def getnote_cmd(client, message):
    em = Emoji(client)
    await em.get()

    xx = await animate_proses(message, em.proses)

    try:
        if len(message.text.split()) == 2:
            note = message.text.split()[1]
            data = await dB.get_var(client.me.id, note, "notes")
            if not data:
                return await xx.edit(f"{em.gagal}**Note {note} not found!**")
            return await getnotes_(client, message, xx, note, data)
        elif len(message.text.split()) == 3 and (message.text.split())[2] in [
            "noformat",
            "raw",
        ]:
            note = message.text.split()[1]
            data = await dB.get_var(client.me.id, note, "notes")
            if not data:
                return await xx.edit(f"{em.gagal}**Note {note} not found!**")
            return await get_raw_note(client, message, xx, note, data)
        else:
            return await xx.edit(f"{em.gagal}**Please give note name!**")
    except Exception as e:
        return await xx.edit(f"{em.gagal}**ERROR**: {str(e)}")


async def getnotes_(client, message, xx, note, data):
    em = Emoji(client)
    await em.get()
    thetext = data["result"].get("text")
    uniq = str(uuid4())
    _, button = ButtonUtils.parse_msg_buttons(thetext)

    if button:
        state.set(client.me.id, "in_notes", id(message))
        try:
            inline = await ButtonUtils.send_inline_bot_result(
                message,
                message.chat.id,
                bot.me.username,
                f"get_note {uniq.split('-')[0]} {note}",
                reply_to_message_id=Message.ReplyCheck(message),
            )
            if inline:
                return await xx.delete()
        except Exception as e:
            return await xx.edit(f"{em.gagal}**ERROR:** {str(e)}")
    else:
        type = data["type"]
        file_id = data["file_id"]

        if type == "text":
            entities = [
                Tools.convert_entity(ent) for ent in data["result"].get("entities", [])
            ]
            await message.reply(
                data["result"].get("text"),
                entities=entities,
                reply_to_message_id=Message.ReplyCheck(message),
            )
            return await xx.delete()
        else:
            pre_senders = {
                "photo": bot.send_photo,
                "voice": bot.send_voice,
                "audio": bot.send_audio,
                "video": bot.send_video,
                "animation": bot.send_animation,
                "document": bot.send_document,
                "sticker": bot.send_sticker,
                "video_note": bot.send_video_note,
            }
            reply_senders = {
                "photo": message.reply_photo,
                "voice": message.reply_voice,
                "audio": message.reply_audio,
                "video": message.reply_video,
                "animation": message.reply_animation,
                "document": message.reply_document,
                "sticker": message.reply_sticker,
                "video_note": message.reply_video_note,
            }
            file_attrs = {
                "photo": "photo",
                "voice": "voice",
                "audio": "audio",
                "video": "video",
                "animation": "animation",
                "document": "document",
                "sticker": "sticker",
                "video_note": "video_note",
            }

            try:
                didel = await pre_senders[type](client.me.id, file_id)
                async for media in client.search_messages(bot.username, limit=1):
                    media_obj = getattr(media, file_attrs[type], None)
                    new_fileid = (
                        getattr(media_obj, "file_id", None) if media_obj else None
                    )
                    break
                else:
                    new_fileid = None

                if not new_fileid:
                    return await message.reply(f"{em.gagal}**Error!! data not found.**")
                await bot.delete_messages(bot.username, didel.id)
                kwargs = {"reply_to_message_id": Message.ReplyCheck(message)}
                if type not in ["sticker", "video_note"]:
                    kwargs["caption"] = data["result"].get("text")
                    kwargs["caption_entities"] = [
                        Tools.convert_entity(ent)
                        for ent in data["result"].get("entities", [])
                    ]

                await reply_senders[type](new_fileid, **kwargs)

            except Exception as e:
                await message.reply(f"{em.gagal}**Send failed:** `{e}`")

        return await xx.delete()


async def get_raw_note(client, message, xx, note, data):
    em = Emoji(client)
    await em.get()
    thetext = data["result"].get("text")
    _, button = ButtonUtils.parse_msg_buttons(thetext)
    try:
        if button:
            type = data["type"]
            file_id = data["file_id"]
            if type == "text":
                await message.reply(
                    data["result"].get("text"),
                    parse_mode=ParseMode.DISABLED,
                    reply_to_message_id=Message.ReplyCheck(message),
                )
            else:
                kwargs = {
                    "photo": bot.send_photo,
                    "voice": bot.send_voice,
                    "audio": bot.send_audio,
                    "video": bot.send_video,
                    "animation": bot.send_animation,
                    "document": bot.send_document,
                }
                if type in kwargs:
                    disend = await kwargs[type](
                        client.me.id,
                        file_id,
                        caption=data["result"].get("text"),
                        parse_mode=ParseMode.DISABLED,
                    )
                    async for copy_msg in client.search_messages(bot.id, limit=1):
                        await copy_msg.copy(message.chat.id)
                        break
                    await disend.delete()

        else:
            type = data["type"]
            file_id = data["file_id"]

            if type == "text":
                await message.reply(
                    data["result"].get("text"),
                    parse_mode=ParseMode.DISABLED,
                    reply_to_message_id=Message.ReplyCheck(message),
                )
            elif type == "sticker":
                await message.reply_sticker(
                    file_id,
                    reply_to_message_id=Message.ReplyCheck(message),
                )
            elif type == "video_note":
                await message.reply_video_note(
                    file_id, reply_to_message_id=Message.ReplyCheck(message)
                )
            else:
                kwargs = {
                    "photo": message.reply_photo,
                    "voice": message.reply_voice,
                    "audio": message.reply_audio,
                    "video": message.reply_video,
                    "animation": message.reply_animation,
                    "document": message.reply_document,
                }

                if type in kwargs:
                    await kwargs[type](
                        file_id,
                        caption=data["result"].get("text"),
                        parse_mode=ParseMode.DISABLED,
                        reply_to_message_id=Message.ReplyCheck(message),
                    )
    except Exception as er:
        logger.info(f"ERROR: {traceback.format_exc()}")
        return await message.reply(f"{em.gagal}**ERROR**: {str(er)}")
    return await xx.delete()


async def listnotes_cmd(client, message):
    em = Emoji(client)
    await em.get()

    xx = await animate_proses(message, em.proses)
    getnotes = await dB.all_var(client.me.id, "notes")
    if not getnotes:
        return await xx.edit(f"{em.gagal}**You dont have any notes!**")
    rply = f"{em.msg}**List of Notes:**\n\n"
    for x, data in getnotes.items():
        type = await dB.get_var(client.me.id, x, "notes")
        rply += f"**• Name: `{x}` | Type: `{type['type']}`**\n"
    return await xx.edit(rply)


async def clearnotes_cmd(client, message):
    em = Emoji(client)
    await em.get()
    args = client.get_arg(message).split(",")

    xx = await animate_proses(message, em.proses)

    if len(args) == 0 or (len(args) == 1 and args[0].strip() == ""):
        return await xx.edit(f"{em.gagal}**Which note do you want to delete?**")
    if message.command[1] == "all":
        for nama in await dB.all_var(client.me.id, "notes"):
            data = await dB.get_var(client.me.id, nama, "notes")
            await dB.remove_var(client.me.id, nama, "notes")
        return await xx.edit(f"{em.sukses}**Succesfully deleted all notes!**")
    else:
        gagal_list = []
        sukses_list = []

        for arg in args:
            arg = arg.strip()
            if not arg:
                continue
            data = await dB.get_var(client.me.id, arg, "notes")
            if not data:
                gagal_list.append(arg)
            else:
                await dB.remove_var(client.me.id, arg, "notes")
                sukses_list.append(arg)

        if sukses_list:
            return await xx.edit(
                f"{em.sukses}**Note `{', '.join(sukses_list)}` successfully deleted.**"
            )

        if gagal_list:
            return await xx.edit(
                f"{em.gagal}**Note `{', '.join(gagal_list)}` not found!**"
            )
