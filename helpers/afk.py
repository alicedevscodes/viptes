import asyncio
import time
import traceback
from collections import defaultdict

from clients import bot
from database import dB, state

from .emoji_logs import Emoji
from .tools import Tools

afk_spam_tracker = defaultdict(list)


class AFK_:
    @staticmethod
    async def set_afk(client, message):
        emo = Emoji(client)
        await emo.get()
        try:
            rep = message.reply_to_message
            if not rep:
                return await message.reply(
                    f"{emo.gagal}<b>Please reply to message!!</b>"
                )
            text = rep.text or rep.caption or ""
            entities = rep.entities or rep.caption_entities
            if rep.media:
                copy = await rep.copy(bot.me.username)
                sent = await client.send_message(
                    bot.me.username, f"/id afk", reply_to_message_id=copy.id
                )
                await asyncio.sleep(1)
                await sent.delete()
                await copy.delete()
                extract = Tools.dump_entity(text, entities)
                type = state.get(client.me.id, "afk")
                value = {
                    "type": type["type"],
                    "file_id": type["file_id"],
                    "result": extract,
                }
            else:
                extract = Tools.dump_entity(text, entities)
                value = {"type": "text", "file_id": "", "result": extract}
            if value:
                await dB.set_var(client.me.id, "AFK", value)

            return await message.reply(
                f"{emo.sukses}**AFK status set to: [this]({rep.link})"
            )
        except Exception as er:
            return await message.reply(f"{emo.gagal}**ERROR**: `{str(er)}`")

    @staticmethod
    async def get_afk(client, message):
        emo = Emoji(client)
        await emo.get()
        try:
            data = await dB.get_var(client.me.id, "AFK")
            if not data:
                return
            ignored = await dB.get_list_from_var(client.me.id, "IGNORE")
            if message.from_user.id in ignored:
                return
            now = time.time()
            afk_spam_tracker[message.from_user.id] = [
                t for t in afk_spam_tracker[message.from_user.id] if now - t < 10
            ]
            afk_spam_tracker[message.from_user.id].append(now)

            if len(afk_spam_tracker[message.from_user.id]) >= 5:
                await dB.add_to_var(client.me.id, "IGNORE", message.from_user.id)
                return
            type = data["type"]
            file_id = data["file_id"]

            if type == "text":
                entities = [
                    Tools.convert_entity(ent)
                    for ent in data["result"].get("entities", [])
                ]
                await message.reply(
                    data["result"].get("text"),
                    entities=entities,
                    reply_to_message_id=message.id,
                )
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
                        return await message.reply("**Error!! data not found.**")
                    kwargs = {"reply_to_message_id": message.id}
                    if type not in ["sticker", "video_note"]:
                        kwargs["caption"] = data["result"].get("text")
                        kwargs["caption_entities"] = [
                            Tools.convert_entity(ent)
                            for ent in data["result"].get("entities", [])
                        ]

                    await reply_senders[type](new_fileid, **kwargs)
                    await bot.delete_messages(bot.username, didel.id)
                except Exception:
                    return await message.reply(
                        f"**Send failed:** `{traceback.format_exc()}`"
                    )
        except Exception:
            return

    @staticmethod
    async def unset_afk(client, message):
        emo = Emoji(client)
        await emo.get()
        vars = await dB.get_var(client.me.id, "AFK")
        if vars:
            await dB.remove_var(client.me.id, "AFK")
            afk_text = f"<b>{emo.sukses}Back to Online!!</b>"
            try:
                ae = await message.reply(afk_text)
                await asyncio.sleep(3)
                return await ae.delete()
            except Exception:
                return
