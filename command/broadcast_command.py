import asyncio
import os

from pyrogram.enums import ChatType
from pyrogram.errors import (ChannelPrivate, ChatSendPlainForbidden,
                             ChatWriteForbidden, FloodWait, Forbidden,
                             NotAcceptable, PeerIdInvalid, SlowmodeWait,
                             UserBannedInChannel)

from clients import bot
from config import BLACKLIST_GCAST, DEVS
from database import dB, state
from helpers import ButtonUtils, Emoji, Tools, animate_proses, task


async def bc_cmd(client, message):
    em = Emoji(client)
    await em.get()
    pong_, uptime_, owner_, ubot_, proses_, sukses_ = await em.get_costum_text()
    proses = await animate_proses(message, em.proses)

    command, text = client.extract_type_and_msg(message)

    if command not in ["group", "private", "all", "db"] or not text:
        return await proses.edit(
            f"{em.gagal}<code>{message.text.split()[0]}</code> <b>[group, private, all atau db]</b>"
        )
    task_id = task.start_task()
    prefix = client.get_prefix(client.me.id)
    await proses.edit(
        f"{em.proses}<i>Task broadcast running #<code>{task_id}</code>. "
        f"Type <code>{prefix[0]}cancel {task_id}</code> to cancel broadcast!</i>"
    )
    peer = client._get_my_peer.get(client.me.id)
    if not peer:
        chats = await client.get_chat_id(command)
    else:
        if len(peer.get(command, [])) != 0:
            chats = peer[command]
        else:
            chats = await client.get_chat_id(command)
    blacklist = await dB.get_list_from_var(client.me.id, "BLACKLIST_GCAST")
    done, failed = 0, 0
    error = f"{em.gagal}**Error failed broadcast:**\n"
    try:
        if command == "db":
            return await broadcast_db(
                client,
                message,
                em,
                prefix,
                done,
                failed,
                blacklist,
                task,
                task_id,
                proses,
            )
        for chat_id in chats:
            if not task.is_active(task_id):
                return await proses.edit(f"{em.gagal}Broadcast cancelled.")
            if chat_id in blacklist or chat_id in BLACKLIST_GCAST or chat_id in DEVS:
                continue
            try:
                await (
                    text.copy(chat_id)
                    if message.reply_to_message
                    else client.send_message(chat_id, text)
                )
                done += 1
            except ChannelPrivate:
                error += f"ChannelPrivate or channel private {chat_id}\n"
                continue

            except SlowmodeWait:
                error += f"SlowmodeWait or gc di timer {chat_id}\n"
                failed += 1
                continue

            except ChatWriteForbidden:
                error += f"ChatWriteForbidden or lu dimute {chat_id}\n"
                failed += 1
                continue

            except Forbidden:
                error += f"Forbidden or antispam grup aktif {chat_id}\n"
                failed += 1
                continue

            except ChatSendPlainForbidden:
                error += f"ChatSendPlainForbidden or ga bisa kirim teks {chat_id}\n"
                failed += 1
                continue

            except UserBannedInChannel:
                error += f"UserBannedInChannel or lu limit {chat_id}\n"
                failed += 1
                continue

            except PeerIdInvalid:
                error += f"PeerIdInvalid or lu bukan pengguna grup ini {chat_id}\n"
                continue
            except NotAcceptable:
                error += f"Grup kontol kirim pesan suruh bayar {chat_id}\n"
                continue

            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await (
                        text.copy(chat_id)
                        if message.reply_to_message
                        else client.send_message(chat_id, text)
                    )
                except Exception:
                    failed += 1
                    continue
                except SlowmodeWait:
                    failed += 1
                    error += f"Grup timer {chat_id}\n"
                    continue

            except Exception as err:
                failed += 1
                error += f"{str(err)}\n"
                continue
    finally:
        task.end_task(task_id)
        await proses.delete()
    if error:
        error_dir = "storage/cache"
        if not os.path.exists(error_dir):
            os.makedirs(error_dir)
        with open(f"{error_dir}/{client.me.id}_errors.txt", "w") as error_file:
            error_file.write(error)
        return await message.reply(
            f"""
<blockquote><b> {em.warn}{sukses_}</b>
<b>{em.sukses}Success: {done}</b>
<b>{em.gagal}Failed: {failed}</b>
<b>{em.msg}Type: {command}</b>
<b>{em.robot}Task ID: `{task_id}`</b>
<b>{em.profil}{owner_}</b>

<b>Type <code>{prefix[0]}bc-error</code> to view failed in broadcast.</b></blockquote>"""
        )
    else:
        return await message.reply(
            f"""
<blockquote><b> {em.warn}{sukses_}</b>
<b>{em.sukses}Success: {done}</b>
<b>{em.gagal}Failed: {failed}</b>
<b>{em.msg}Type: {command}</b>
<b>{em.robot}Task ID: `{task_id}`</b>
<b>{em.profil}{owner_}</b></blockquote>"""
        )


async def gcast_cmd(client, message):
    em = Emoji(client)
    await em.get()
    pong_, uptime_, owner_, ubot_, proses_, sukses_ = await em.get_costum_text()
    proses = await animate_proses(message, em.proses)

    text = client.get_message(message)

    if not text:
        return await proses.edit(
            f"{em.gagal}<code>{message.text.split()[0]}</code> <b>text or give text</b>"
        )
    task_id = task.start_task()
    prefix = client.get_prefix(client.me.id)
    await proses.edit(
        f"{em.proses}<i>Task {message.command[0]} running #<code>{task_id}</code>. "
        f"Type <code>{prefix[0]}cancel {task_id}</code> to cancel {message.command[0]}!</i>"
    )
    peer = client._get_my_peer.get(client.me.id)
    if not peer:
        chats = await client.get_chat_id("group")
    else:
        if len(peer.get("group", [])) != 0:
            chats = peer["group"]
        else:
            chats = await client.get_chat_id("group")
    blacklist = await dB.get_list_from_var(client.me.id, "BLACKLIST_GCAST")
    done, failed = 0, 0
    error = f"{em.gagal}**Error failed broadcast:**\n"
    try:

        for chat_id in chats:
            if not task.is_active(task_id):
                return await proses.edit(f"{em.gagal}{message.command[0]} cancelled.")
            if chat_id in blacklist or chat_id in BLACKLIST_GCAST or chat_id in DEVS:
                continue
            try:
                await (
                    text.copy(chat_id)
                    if message.reply_to_message
                    else client.send_message(chat_id, text)
                )
                done += 1
            except ChannelPrivate:
                error += f"ChannelPrivate or channel private {chat_id}\n"
                continue

            except SlowmodeWait:
                error += f"SlowmodeWait or gc di timer {chat_id}\n"
                failed += 1
                continue

            except ChatWriteForbidden:
                error += f"ChatWriteForbidden or lu dimute {chat_id}\n"
                failed += 1
                continue

            except Forbidden:
                error += f"Forbidden or antispam grup aktif {chat_id}\n"
                failed += 1
                continue

            except ChatSendPlainForbidden:
                error += f"ChatSendPlainForbidden or ga bisa kirim teks {chat_id}\n"
                failed += 1
                continue

            except UserBannedInChannel:
                error += f"UserBannedInChannel or lu limit {chat_id}\n"
                failed += 1
                continue

            except PeerIdInvalid:
                error += f"PeerIdInvalid or lu bukan pengguna grup ini {chat_id}\n"
                continue
            except NotAcceptable:
                error += f"Grup kontol kirim pesan suruh bayar {chat_id}\n"
                continue

            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await (
                        text.copy(chat_id)
                        if message.reply_to_message
                        else client.send_message(chat_id, text)
                    )
                except Exception:
                    failed += 1
                    continue
                except SlowmodeWait:
                    failed += 1
                    error += f"Grup timer {chat_id}\n"
                    continue

            except Exception as err:
                failed += 1
                error += f"{str(err)}\n"
                continue
    finally:
        task.end_task(task_id)
        await proses.delete()
    if error:
        error_dir = "storage/cache"
        if not os.path.exists(error_dir):
            os.makedirs(error_dir)
        with open(f"{error_dir}/{client.me.id}_errors.txt", "w") as error_file:
            error_file.write(error)
        return await message.reply(
            f"""
<blockquote><b> {em.warn}{sukses_}</b>
<b>{em.sukses}Success: {done}</b>
<b>{em.gagal}Failed: {failed}</b>
<b>{em.msg}Type: {message.command[0]}</b>
<b>{em.robot}Task ID: `{task_id}`</b>
<b>{em.profil}{owner_}</b>

<b>Type <code>{prefix[0]}bc-error</code> to view failed in broadcast.</b></blockquote>"""
        )
    else:
        return await message.reply(
            f"""
<blockquote><b> {em.warn}{sukses_}</b>
<b>{em.sukses}Success: {done}</b>
<b>{em.gagal}Failed: {failed}</b>
<b>{em.msg}Type: {message.command[0]}</b>
<b>{em.robot}Task ID: `{task_id}`</b>
<b>{em.profil}{owner_}</b></blockquote>"""
        )


async def ucast_cmd(client, message):
    em = Emoji(client)
    await em.get()
    pong_, uptime_, owner_, ubot_, proses_, sukses_ = await em.get_costum_text()
    proses = await animate_proses(message, em.proses)

    text = client.get_message(message)

    if not text:
        return await proses.edit(
            f"{em.gagal}<code>{message.text.split()[0]}</code> <b>text or give text</b>"
        )
    task_id = task.start_task()
    prefix = client.get_prefix(client.me.id)
    await proses.edit(
        f"{em.proses}<i>Task {message.command[0]} running #<code>{task_id}</code>. "
        f"Type <code>{prefix[0]}cancel {task_id}</code> to cancel {message.command[0]}!</i>"
    )
    peer = client._get_my_peer.get(client.me.id)
    if not peer:
        chats = await client.get_chat_id("private")
    else:
        if len(peer.get("private", [])) != 0:
            chats = peer["private"]
        else:
            chats = await client.get_chat_id("private")
    blacklist = await dB.get_list_from_var(client.me.id, "BLACKLIST_GCAST")
    done, failed = 0, 0
    error = f"{em.gagal}**Error failed broadcast:**\n"
    try:
        for chat_id in chats:
            if not task.is_active(task_id):
                return await proses.edit(f"{em.gagal}{message.command[0]} cancelled.")
            if chat_id in blacklist or chat_id in BLACKLIST_GCAST or chat_id in DEVS:
                continue
            try:
                await (
                    text.copy(chat_id)
                    if message.reply_to_message
                    else client.send_message(chat_id, text)
                )
                done += 1
            except ChannelPrivate:
                error += f"ChannelPrivate or channel private {chat_id}\n"
                continue

            except ChatWriteForbidden:
                error += f"ChatWriteForbidden or lu dimute {chat_id}\n"
                failed += 1
                continue

            except Forbidden:
                error += f"Forbidden or antispam grup aktif {chat_id}\n"
                failed += 1
                continue

            except UserBannedInChannel:
                error += f"UserBannedInChannel or lu limit {chat_id}\n"
                failed += 1
                continue

            except PeerIdInvalid:
                error += f"PeerIdInvalid or lu bukan pengguna grup ini {chat_id}\n"
                continue

            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await (
                        text.copy(chat_id)
                        if message.reply_to_message
                        else client.send_message(chat_id, text)
                    )
                except Exception:
                    failed += 1
                    continue
            except Exception as err:
                failed += 1
                error += f"{str(err)}\n"
                continue
    finally:
        task.end_task(task_id)
        await proses.delete()
    if error:
        error_dir = "storage/cache"
        if not os.path.exists(error_dir):
            os.makedirs(error_dir)
        with open(f"{error_dir}/{client.me.id}_errors.txt", "w") as error_file:
            error_file.write(error)
        return await message.reply(
            f"""
<blockquote><b> {em.warn}{sukses_}</b>
<b>{em.sukses}Success: {done}</b>
<b>{em.gagal}Failed: {failed}</b>
<b>{em.msg}Type: {message.command[0]}</b>
<b>{em.robot}Task ID: `{task_id}`</b>
<b>{em.profil}{owner_}</b>

<b>Type <code>{prefix[0]}bc-error</code> to view failed in broadcast.</b></blockquote>"""
        )
    else:
        return await message.reply(
            f"""
<blockquote><b> {em.warn}{sukses_}</b>
<b>{em.sukses}Success: {done}</b>
<b>{em.gagal}Failed: {failed}</b>
<b>{em.msg}Type: {message.command[0]}</b>
<b>{em.robot}Task ID: `{task_id}`</b>
<b>{em.profil}{owner_}</b></blockquote>"""
        )


async def bcerror_cmd(client, message):
    oy = await message.reply("<b>Reading error logs...</b>")
    try:
        error_file = f"storage/cache/{client.me.id}_errors.txt"
        try:
            with open(error_file, "r") as f:
                content = f.read().strip()

            if not content:
                await oy.edit("<b>No errors found in log file.</b>")
                return
            if len(content) > 4000:
                content = content[-4000:]
                content = f"... (truncated)\n\n{content}"

            message_text = f"<b>📋 Error Logs:</b>\n\n<code>{content}</code>"

            return await oy.edit(message_text)

        except FileNotFoundError:
            return await oy.edit("<b>Error log file not found!</b>")

    except Exception:
        try:
            error_file = f"storage/cache/{client.me.id}_error.txt"
            with open(error_file, "r") as f:
                content = f.read().strip()

            if not content:
                await oy.edit("<b>No errors found in fallback log file.</b>")
                return

            if len(content) > 4000:
                content = content[-4000:]
                content = f"... (truncated)\n\n{content}"

            message_text = (
                f"<b>📋 Error Logs (from fallback):</b>\n\n<code>{content}</code>"
            )

            await client.send_message("me", message_text)
            return await oy.edit("<b>Cek saved message</b>")

        except Exception as e:
            return await oy.edit(f"<b>Failed to read error logs: {str(e)}</b>")


async def broadcast_db(
    client, message, em, prefix, done, failed, blacklist, task, task_id, proses
):
    command, text = client.extract_type_and_msg(message)
    pong_, uptime_, owner_, ubot_, proses_, sukses_ = await em.get_costum_text()
    chatsdb = await dB.get_list_from_var(client.me.id, "BROADCASTDB")
    if not chatsdb:
        return await proses.edit(
            f"{em.gagal}**You don't have broadcastdb !!Please type `{prefix[0]} add-bcdb 'in the group or user.**"
        )
    try:
        for chat_id in chatsdb:
            if not task.is_active(task_id):
                return await proses.edit(f"{em.gagal}**Broadcast cancelled.**")
            if chat_id in blacklist or chat_id in BLACKLIST_GCAST or chat_id in DEVS:
                continue
            try:
                await (
                    text.copy(chat_id)
                    if message.reply_to_message
                    else client.send_message(chat_id, text)
                )
                done += 1
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await (
                    text.copy(chat_id)
                    if message.reply_to_message
                    else client.send_message(chat_id, text)
                )
            except Exception:
                failed += 1
                continue
    finally:
        task.end_task(task_id)
        await proses.delete()

    return await message.reply(
        f"""
<blockquote><b> {em.warn}{sukses_}</b>
<b>{em.sukses}Success: {done}</b>
<b>{em.gagal}Failed: {failed}</b>
<b>{em.msg}Type: {command}</b>
<b>{em.profil}Task ID: {task_id}</b></blockquote>

<blockquote><b>{em.profil}{owner_}</b></blockquote>"""
    )


async def cancel_cmd(client, message):
    em = Emoji(client)
    await em.get()
    prefix = client.get_prefix(client.me.id)
    if len(message.command) != 2:
        return await message.reply(
            f"{em.gagal}**Please provide a task ID to cancel.\nType `{prefix[0]}task` to view list task running.**"
        )

    task_id = message.command[1]

    if not task.is_active(task_id):
        return await message.reply(
            f"{em.gagal}**No active task found with ID: #`{task_id}`**"
        )
    task.end_task(task_id)
    return await message.reply(f"{em.sukses}**Ended task: #`{task_id}`**")


async def addbl_cmd(client, message):
    em = Emoji(client)
    await em.get()
    pp = await animate_proses(message, em.proses)
    chat_id = message.command[1] if len(message.command) > 1 else message.chat.id
    blacklist = await dB.get_list_from_var(client.me.id, "BLACKLIST_GCAST")
    try:
        chat_id = int(chat_id)
    except ValueError:
        return await pp.edit(f"{em.gagal}**chat_id must be in the form of numbers!**")
    chat_type = await client.get_chat(chat_id)
    if chat_type.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        name = chat_type.title
    elif chat_type.type == ChatType.PRIVATE:
        name = f"{chat_type.first_name} {chat_type.last_name or ''}"
    if chat_id in blacklist:
        return await pp.edit(f"{em.gagal}**`{name}` already in the blacklist-Gcast!**")
    await dB.add_to_var(client.me.id, "BLACKLIST_GCAST", chat_id)
    return await pp.edit(
        f"{em.sukses}<b>Successfully adding `{name}` into blacklists</b>"
    )


async def delbl_cmd(client, message):
    em = Emoji(client)
    await em.get()

    pp = await animate_proses(message, em.proses)
    blacklist = await dB.get_list_from_var(client.me.id, "BLACKLIST_GCAST")
    try:
        if len(message.command) < 2:
            chat_id = message.chat.id
            chat_type = await client.get_chat(chat_id)
            if chat_type.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                name = chat_type.title
            elif chat_type.type == ChatType.PRIVATE:
                name = f"{chat_type.first_name} {chat_type.last_name or ''}"
            if chat_id not in blacklist:
                return await pp.edit(f"{em.gagal}**`{name}` is not in blacklists!**")
            await dB.remove_from_var(client.me.id, "BLACKLIST_GCAST", chat_id)
            return await pp.edit(
                f"{em.sukses}**Successfully delete `{name}` from the blacklist-gcast list!**"
            )
        else:
            if message.command[1] == "all":
                for A in blacklist:
                    await dB.remove_from_var(client.me.id, "BLACKLIST_GCAST", A)
                return await pp.edit(
                    f"{em.sukses}<b>Successfully delete all blacklist-gcast lists!</b>"
                )
            else:
                chat_id = message.command[1]
                try:
                    chat_id = int(chat_id)
                except ValueError:
                    return await pp.edit(
                        f"{em.gagal}**Please give a valid chat_id.Error `{chat_id}`!**"
                    )
                chat_type = await client.get_chat(chat_id)
                if chat_type.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                    name = chat_type.title
                elif chat_type.type == ChatType.PRIVATE:
                    name = f"{chat_type.first_name} {chat_type.last_name or ''}"
                if chat_id not in blacklist:
                    return await pp.edit(
                        f"{em.gagal}`{name}` **Not in Blacklist-Gcast!**"
                    )
                await dB.remove_from_var(client.me.id, "BLACKLIST_GCAST", chat_id)
                return await pp.edit(
                    f"{em.sukses}**Successfully delete `{name}` from the blacklist-gcast list!**"
                )
    except Exception as er:
        return await pp.edit(f"{em.gagal}ERRORR: `{str(er)}`!!")


async def listbl_cmd(client, message):
    em = Emoji(client)
    await em.get()

    blacklist = await dB.get_list_from_var(client.me.id, "BLACKLIST_GCAST")
    pp = await animate_proses(message, em.proses)
    if blacklist == []:
        return await pp.edit(f"{em.gagal}**Your Blacklist-Gcast Data is still empty!**")
    msg = f"{em.msg}Total Blacklist-Gcast: {len(blacklist)}\n\n"
    for num, x in enumerate(blacklist, 1):
        try:
            chat = await client.get_chat(x)
            name = chat.title or f"{chat.first_name} {chat.last_name or ''}"
            msg += f"{num}. {name}|`{chat.id}`\n"
        except Exception:
            msg += f"{num}. `{x}`\n"
    if len(msg) > 4096:
        link = await Tools.paste(msg)
        await pp.edit(f"{em.proses}**Message is too long, uploading to pastebin...**")
        await asyncio.sleep(1)
        return await message.reply_text(
            f"{em.sukses}**<a href='{link}'>Click here </a> to see your blacklist-gcast list.**",
            disable_web_page_preview=True,
        )
    else:
        await pp.delete()
        return await message.reply_text(msg)


async def addbcdb_cmd(client, message):
    em = Emoji(client)
    await em.get()
    pp = await animate_proses(message, em.proses)
    chat_id = message.chat.id if len(message.command) > 1 else message.command[1]
    blacklist = await dB.get_list_from_var(client.me.id, "BROADCASTDB")
    chat_type = await client.get_chat(chat_id)
    if chat_type.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        name = chat_type.title
    elif chat_type.type == ChatType.PRIVATE:
        name = f"{chat_type.first_name} {chat_type.last_name or ''}"
    try:
        chat_id = int(chat_id)
    except ValueError:
        return await pp.edit(f"{em.gagal}**Chat_id must be a number!**")

    if chat_id in blacklist:
        return await pp.edit(f"{em.gagal}`{name}` **Already on Broadcast-DB!**")
    await dB.add_to_var(client.me.id, "BROADCASTDB", chat_id)
    return await pp.edit(
        f"{em.sukses}**Successfully added `{name}` into broadcast-db**"
    )


async def delbcdb_cmd(client, message):
    em = Emoji(client)
    await em.get()
    pp = await animate_proses(message, em.proses)
    blacklist = await dB.get_list_from_var(client.me.id, "BROADCASTDB")
    try:
        if len(message.command) < 2:
            chat_id = message.chat.id
            chat_type = await client.get_chat(chat_id)
            if chat_type.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                name = chat_type.title
            elif chat_type.type == ChatType.PRIVATE:
                name = f"{chat_type.first_name} {chat_type.last_name or ''}"
            if chat_id not in blacklist:
                return await pp.edit(f"{em.gagal}`{name}` **is not in broadcast-db!**")
            await dB.remove_from_var(client.me.id, "BROADCASTDB", chat_id)
            return await pp.edit(
                f"{em.sukses}**Successfully delete `{name} 'from the broadcast list-db!**"
            )
        else:
            if message.command[1] == "all":
                for A in blacklist:
                    await dB.remove_from_var(client.me.id, "BROADCASTDB", A)
                return await pp.edit(
                    f"{em.sukses}Successfully delete all broadcast lists-DB!"
                )
            else:
                chat_id = message.command[1]
                try:
                    chat_id = int(chat_id)
                except ValueError:
                    return await pp.edit(
                        f"{em.gagal}**Please give a valid chat_id.Error `{chat_id}`!**"
                    )
                chat_type = await client.get_chat(chat_id)
                if chat_type.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                    name = chat_type.title
                elif chat_type.type == ChatType.PRIVATE:
                    name = f"{chat_type.first_name} {chat_type.last_name or ''}"
                if chat_id not in blacklist:
                    return await pp.edit(f"{em.gagal}`{name}` **not in broadcast-db!**")
                await dB.remove_from_var(client.me.id, "BROADCASTDB", chat_id)
                return await pp.edit(
                    f"{em.sukses}**Successfully delete `{name}` from the broadcast list-db!**"
                )
    except Exception as er:
        return await pp.edit(f"{em.gagal}ERRORR: `{str(er)}`!!")


async def listbcdb_cmd(client, message):
    em = Emoji(client)
    await em.get()

    blacklist = await dB.get_list_from_var(client.me.id, "BROADCASTDB")
    pp = await animate_proses(message, em.proses)
    if blacklist == []:
        return await pp.edit(f"{em.gagal}**Your broadcast-DB data is still empty!**")
    msg = f"{em.msg}**Total Broadcast-DB: {len(blacklist)}**\n\n"
    for num, x in enumerate(blacklist, 1):
        try:
            chat = await client.get_chat(x)
            name = chat.title or f"{chat.first_name} {chat.last_name or ''}"
            msg += f"**{num}. {name}|`{chat.id}`**\n"
        except Exception:
            msg += f"**{num}. `{x}`**\n"
    if len(msg) > 4096:
        link = await Tools.paste(msg)
        await pp.edit(f"{em.proses}**Message is too long, uploading to pastebin ...**")
        await asyncio.sleep(1)
        return await message.reply_text(
            f"{em.sukses}**<a href='{link}'>Click here </a> to see your broadcast list.**",
            disable_web_page_preview=True,
        )
    else:
        await pp.delete()
        return await message.reply_text(msg)


async def sendinline_cmd(client, message):
    em = Emoji(client)
    await em.get()
    if message.reply_to_message:
        chat_id = (
            message.chat.id if len(message.command) < 2 else message.text.split()[1]
        )
        try:
            if message.reply_to_message.reply_markup:
                state.set(client.me.id, "inline_send", id(message))
                query = f"inline_send {client.me.id}"
                inline = await ButtonUtils.send_inline_bot_result(
                    message,
                    chat_id,
                    bot.me.username,
                    query,
                )
                if inline:
                    return await message.delete()
        except Exception as er:
            return await message.reply(f"{em.gagal}ERROR: {str(er)}")
        else:
            try:
                await message.reply_to_message.copy(chat_id)
                await message.delete()
                return
            except Exception as er:
                return await message.reply(f"{em.gagal}ERROR: {str(er)}")
    else:
        if len(message.command) < 3:
            return
        chat_id, chat_text = message.text.split(None, 2)[1:]
        try:
            if "/" in chat_id:
                to_chat, msg_id = chat_id.split("/")
                await client.send_message(
                    to_chat, chat_text, reply_to_message_id=int(msg_id)
                )
                await message.delete()
                return
            else:
                await client.send_message(chat_id, chat_text)
                await message.delete()
                return
        except Exception as er:
            return await message.reply(f"{em.gagal}ERROR: {str(er)}")


async def spam_cmd(client, message):
    emo = Emoji(client)
    await emo.get()
    command = message.command[0]
    reply = message.reply_to_message
    proses = await client.send_message(
        "me",
        f"{emo.proses}<b>{'Delay ' if command == 'dspam' else ''}Spam process is running ..</b>",
    )
    task_id = task.start_task()
    prefix = client.get_prefix(client.me.id)
    try:
        if len(message.command) < 2:
            return await proses.edit(
                f"{emo.gagal}<b>Usage `{prefix[0]}{command}`[amount] {'[delay] ' if command == 'dspam' else ''}[text/reply text].</b>"
            )
        jumlah = int(message.command[1])
        count_delay = (
            int(message.command[2])
            if command == "dspam" and len(message.command) > 2
            else 0
        )
    except Exception as error:
        return await proses.edit(f"{emo.gagal}<b>Error:</b>\n<code>{str(error)}</code>")
    await proses.edit(
        f"{emo.proses}<i>{'Delay ' if command == 'dspam' else ''}Spam task running #<code>{task_id}</code>. "
        f"Type <code>{prefix[0]}cancel {task_id}</code> to cancel {'delay ' if command == 'dspam' else ''}spam!</i>"
    )
    if reply:
        text = reply.text
    else:
        if len(message.command) < (3 if command == "dspam" else 2):
            return await proses.edit(
                f"{emo.gagal}<b>Usage `{prefix[0]}{command}`[amount] {'[delay] ' if command == 'dspam' else ''}[text/reply text].</b>"
            )
        text = message.text.split(None, 3 if command == "dspam" else 2)[-1]
    for i in range(jumlah):
        if not task.is_active(task_id):
            return await proses.edit(
                f"{emo.gagal}{'Delay ' if command == 'dspam' else ''}Spam cancelled."
            )
        else:
            while True:
                try:
                    await (
                        reply.copy(message.chat.id) if reply else message.reply(text)
                    )
                    break
                except (FloodWait, SlowmodeWait) as e:
                    await asyncio.sleep(e.value)
                except Exception as error:
                    return await proses.edit(str(error))
            await asyncio.sleep(count_delay if command == "dspam" else 0.1)

    task.end_task(task_id)
    return await message.delete()


async def spamg_cmd(client, message):
    emo = Emoji(client)
    await emo.get()
    proses = await message.reply(f"{emo.proses}<b>Spam broadcast process ..</b>")
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await proses.edit(
            f"{emo.gagal}<b>Please use command: `{message.text.split()[0]} 5` (text or reply text)</b>"
        )

    jumlah = int(message.command[1])
    send = client.get_message(message)
    if not send:
        return await proses.edit(
            f"{emo.gagal}<b>Provide me with text or reply to a message ..</b>"
        )
    task_id = task.start_task()
    prefix = client.get_prefix(client.me.id)
    await proses.edit(
        f"{emo.proses}<i>Spam broadcast task running #<code>{task_id}</code>. "
        f"Type <code>{prefix[0]}cancel {task_id}</code> to cancel Spam broadcast!</i>"
    )
    chats = await client.get_chat_id("group")
    blacklist = await dB.get_list_from_var(client.me.id, "BLACKLIST_GCAST")
    done = 0
    failed = 0
    for chat_id in chats:
        if chat_id in blacklist or chat_id in BLACKLIST_GCAST:
            continue
        if not task.is_active(task_id):
            return await proses.edit(f"{emo.gagal}Spam broadcast cancelled.")
        else:
            try:
                for i in range(jumlah):
                    (
                        await send.copy(chat_id)
                        if message.reply_to_message
                        else await client.send_message(chat_id, send)
                    )
                done += 1
            except FloodWait as e:
                wait = int(e.value)
                if wait > 200:
                    failed += 1
                    continue
                await asyncio.sleep(wait)
                try:
                    for i in range(jumlah):
                        (
                            await send.copy(chat_id)
                            if message.reply_to_message
                            else await client.send_message(chat_id, send)
                        )
                    done += 1
                except Exception:
                    failed += 1
                    continue
            except Exception:
                failed += 1
                continue
    task.end_task(task_id)

    await message.reply(
        f"""
{emo.profil}<b>Spam Broadcast Report:
{emo.sukses} Success: <code>{done}</code> Groups
{emo.gagal} Failed: <code>{failed}</code> Groups
</b>"""
    )
    return await proses.delete()
