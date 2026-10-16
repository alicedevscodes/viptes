import asyncio
import contextlib
import html
import importlib.util
import io
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from time import perf_counter
from typing import Any, Dict
from uuid import uuid4

import pyrogram
import pyrogram.enums
import pyrogram.errors
import pyrogram.helpers
import pyrogram.raw
import pyrogram.types
import pyrogram.utils
from meval import meval
from pytz import timezone

import config
from clients import bot, alice
from database import DB_PATH, dB, state
from helpers import (ButtonUtils, Emoji, Message, Quotly, Sticker,
                     TokenReferal, Tools, task,
                     )
from logs import logger

eval_tasks: Dict[int, Any] = {}

PLUGIN_DIR = "plugins"

loaded_plugins = {}


async def plugins_cmd(_, message):
    if message.command[0] == "loadplugins":
        if (
            not message.reply_to_message.document
            or not message.reply_to_message.document.file_name.endswith(".py")
        ):
            return await message.reply(
                "**Reply ke file .py untuk di-load sebagai plugin.**"
            )

        file_name = message.reply_to_message.document.file_name
        plugin_path = os.path.join(PLUGIN_DIR, file_name)

        await message.reply_to_message.download(file_name=plugin_path)

        try:
            spec = importlib.util.spec_from_file_location(file_name[:-3], plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sys.modules[file_name[:-3]] = module
            loaded_plugins[file_name[:-3]] = module
            module_name = getattr(module, "__MODULES__", "").lower()
            is_pro_plugin = getattr(module, "IS_PRO", False)
            if module_name:
                config.HELPABLE[module_name] = {
                    "module": module,
                    "is_pro": is_pro_plugin,
                }
            await message.reply(f"**✅ Plugin `{file_name}` berhasil di-load.**")
        except Exception as e:
            await message.reply(f"**❌ Gagal load plugin: `{e}`**")
    elif message.command[0] == "unloadplugins":
        if len(message.command) < 2:
            return await message.reply(
                f"**Berikan nama plugin.py untuk di-unload.\nContoh: `{message.text.split()[0]} test.py`**"
            )

        file_name = message.command[1]
        plugin_path = os.path.join(PLUGIN_DIR, file_name)
        module_name = file_name[:-3]

        if module_name in loaded_plugins:
            try:
                del sys.modules[module_name]
                del loaded_plugins[module_name]
                for key in list(config.HELPABLE):
                    if config.HELPABLE[key]["module"].__name__ == module_name:
                        del config.HELPABLE[key]
            except Exception as e:
                return await message.reply(f"**❌ Gagal unload modul: `{e}`**")

        if os.path.exists(plugin_path):
            os.remove(plugin_path)
            return await message.reply(
                f"**✅ Plugin `{file_name}` berhasil di-unload dan dihapus.**"
            )
        else:
            return await message.reply("**❌ File tidak ditemukan di folder plugins.**")
    elif message.command[0] == "listplugins":
        files = sorted(f for f in os.listdir(PLUGIN_DIR) if f.endswith(".py"))
        if not files:
            return await message.reply("**📂 Tidak ada plugin di folder `plugins`.**")

        plugin_list = "\n".join(f"• `{f}`" for f in files)
        await message.reply(f"**📁 Daftar plugin:**\n\n{plugin_list}")


async def send_ubot_1(client, message):
    user = message.from_user if message.from_user else message.sender_chat
    if user.id not in config.DEVA:
        return
    return await client.send_message(
        message.from_user.id,
        await Message.userbot(0),
        reply_markup=ButtonUtils.userbot(alice._ubot[0].me.id, 0),
    )


async def send_ubot_2(client, message):
    user = message.from_user if message.from_user else message.sender_chat
    if user.id not in config.SUDO_OWNERS:
        return
    return await client.send_message(
        message.from_user.id,
        await Message.userbot(0),
        reply_markup=ButtonUtils.fake_userbot(alice._ubot[0].me.id, 0),
    )


async def restore(client, message):
    user = message.from_user if message.from_user else message.sender_chat
    if user.id not in config.DEVA:
        return
    reply = message.reply_to_message
    if not reply:
        return await message.reply("**Please reply to a .db or .zip file**")

    document = reply.document
    file_path = await client.download_media(document, "./")

    if file_path.endswith(".zip"):
        extract_path = "./extracted_db"
        os.makedirs(extract_path, exist_ok=True)

        with zipfile.ZipFile(file_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)

        db_files = [f for f in os.listdir(extract_path) if f.endswith(".db")]
        if not db_files:
            return await message.reply("**No .db file found in the ZIP archive**")

        extracted_db = os.path.join(extract_path, db_files[0])
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        os.rename(extracted_db, DB_PATH)

        os.remove(file_path)
    else:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        document = reply.document
        file_path = await client.download_media(document, "./")
    await message.reply(
        f"<blockquote><b>Sukses melakukan restore database, tunggu sebentar bot akan me-restart.</blockquote></b>"
    )
    os.execl(sys.executable, sys.executable, *sys.argv)


async def backup(client, message):
    user = message.from_user if message.from_user else message.sender_chat
    if user.id not in config.DEVA:
        return
    now = datetime.now(timezone("Asia/Jakarta"))
    timestamp = now.strftime("%Y-%m-%d_%H:%M")
    zip_filename = f"{config.BOT_NAME}_{timestamp}.zip"
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        if os.path.exists(".env"):
            env_path = os.path.abspath(".env")
            token_path = os.path.abspath("token.json")
            zipf.write(env_path, os.path.basename(env_path))
            zipf.write(DB_PATH, os.path.basename(DB_PATH))
            zipf.write(token_path, os.path.basename(token_path))
        else:
            token_path = os.path.abspath("token.json")
            zipf.write(DB_PATH, os.path.basename(DB_PATH))
            zipf.write(token_path, os.path.basename(token_path))
    caption = now.strftime("%d %B %Y %H:%M")
    return await message.reply_document(zip_filename, caption=caption)


async def cb_shell(client, message):
    user = message.from_user if message.from_user else message.sender_chat
    if user.id not in config.DEVA:
        return
    if len(message.command) < 2:
        return await message.reply("Noob!!")
    cmd_text = message.text.split(maxsplit=1)[1]
    text = f"<code>{cmd_text}</code>\n\n"
    start_time = perf_counter()

    try:
        stdout, stderr = await Tools.bash(cmd_text)
    except asyncio.TimeoutError:
        text += "<b>Timeout expired!!</b>"
        return await message.reply(text)
    finally:
        duration = perf_counter() - start_time
    if cmd_text.startswith("cat "):
        filepath = cmd_text.split("cat ", 1)[1].strip()
        output_filename = os.path.basename(filepath)
    else:
        output_filename = f"{cmd_text}.txt"
    if len(stdout) > 4096:
        anuk = await message.reply("<b>Oversize, sending file...</b>")
        with open(output_filename, "w") as file:
            file.write(stdout)

        await message.reply_document(
            output_filename,
            caption=f"<b>Command completed in `{duration:.2f}` seconds.</b>",
        )
        os.remove(output_filename)
        return await anuk.delete()
    else:
        text += f"<pre><code>{stdout}</code></pre>"

        if stderr:
            text += f"<blockquote>{stderr}</blockquote>"
        text += f"\n<b>Completed in `{duration:.2f}` seconds.</b>"
        return await message.reply(text, parse_mode=pyrogram.enums.ParseMode.HTML)


async def cb_evaluasi_bot(client, message):
    user = message.from_user if message.from_user else message.sender_chat
    if user.id not in config.DEVA:
        return
    if len(message.text.split()) == 1:
        await message.reply_text("<b>No Code!</b>", quote=True)
        return

    reply_text = await message.reply_text(
        "...",
        quote=True,
        reply_markup=pyrogram.helpers.ikb([[("Cancel", "Canceleval")]]),
    )

    async def eval_func() -> None:
        eval_code = message.text.split(maxsplit=1)[1]
        eval_vars = {
            # PARAMETERS
            "c": client,
            "m": message,
            "u": (message.reply_to_message or message).from_user,
            "r": message.reply_to_message,
            "chat": message.chat,
            # PYROGRAM
            "asyncio": asyncio,
            "pyrogram": pyrogram,
            "raw": pyrogram.raw,
            "enums": pyrogram.enums,
            "types": pyrogram.types,
            "errors": pyrogram.errors,
            "utils": pyrogram.utils,
            "helpers": pyrogram.helpers,
            # LOCAL
            "bot": bot,
            "alice": alice,
            "dB": dB,
            "Emoji": Emoji,
            "config": config,
            "Message": Message,
            "Tools": Tools,
            "Sticker": Sticker,
            "Quotly": Quotly,       
            "task": task,
            "button": ButtonUtils,
            "state": state,
            "TokenReferal": TokenReferal,
            "DB_PATH": DB_PATH,
        }

        start_time = client.loop.time()

        file = io.StringIO()
        with contextlib.redirect_stdout(file):
            try:
                meval_out = await meval(eval_code, globals(), **eval_vars)
                print_out = file.getvalue().strip() or str(meval_out) or "None"
            except Exception as exception:
                print_out = repr(exception)

        elapsed_time = client.loop.time() - start_time

        converted_time = Tools.convert_seconds(elapsed_time)

        final_output = (
            f"<pre>{html.escape(print_out)}</pre>\n" f"<b>Elapsed:</b> {converted_time}"
        )
        if len(final_output) > 4096:
            paste_url = await Tools.paste(html.escape(print_out))
            await reply_text.edit_text(
                f"<b>Elapsed:</b> {converted_time}",
                reply_markup=pyrogram.helpers.ikb(
                    [[("Output", f"{paste_url}", "url")]]
                ),
                disable_web_page_preview=True,
            )
        else:
            await reply_text.edit_text(final_output)

    task_id = message.id
    _e_task = asyncio.create_task(eval_func())

    eval_tasks[task_id] = _e_task

    try:
        await _e_task
    except asyncio.CancelledError:
        await reply_text.edit_text("<b>Process Cancelled!</b>")
    finally:
        if task_id in eval_tasks:
            del eval_tasks[task_id]


async def cb_evalusi(client, message):
    user = message.from_user if message.from_user else message.sender_chat
    if user.id not in config.DEVA:
        return
    if len(message.text.split()) == 1:
        await message.reply_text("<b>No Code!</b>", quote=True)
        return
    reply_text = await message.reply_text("...", quote=True)
    uniq = f"{str(uuid4())}"

    async def eval_func() -> None:
        eval_code = message.text.split(maxsplit=1)[1]
        eval_vars = {
            # PARAMETERS
            "c": client,
            "m": message,
            "u": (message.reply_to_message or message).from_user,
            "r": message.reply_to_message,
            "chat": message.chat,
            # PYROGRAM
            "asyncio": asyncio,
            "pyrogram": pyrogram,
            "raw": pyrogram.raw,
            "enums": pyrogram.enums,
            "types": pyrogram.types,
            "errors": pyrogram.errors,
            "utils": pyrogram.utils,
            "helpers": pyrogram.helpers,
            # LOCAL
            "bot": bot,
            "alice": alice,
            "dB": dB,
            "Emoji": Emoji,
            "config": config,
            "Message": Message,
            "Tools": Tools,
            "Sticker": Sticker,
            "Quotly": Quotly,
            "task": task,
            "button": ButtonUtils,
            "state": state,
            "TokenReferal": TokenReferal,
            "DB_PATH": DB_PATH,
        }

        start_time = client.loop.time()

        file = io.StringIO()
        with contextlib.redirect_stdout(file):
            try:
                meval_out = await meval(eval_code, globals(), **eval_vars)
                print_out = file.getvalue().strip() or str(meval_out) or "None"
            except Exception as exception:
                print_out = repr(exception)

        elapsed_time = client.loop.time() - start_time

        converted_time = Tools.convert_seconds(elapsed_time)

        final_output = (
            f"<pre>{html.escape(print_out)}</pre>\n" f"<b>Elapsed:</b> {converted_time}"
        )
        if len(final_output) > 4096:
            paste_url = await Tools.paste(html.escape(print_out))
            datas = {"time": f"<b>Elapsed:</b> {converted_time}", "url": paste_url}
            state.set(config.BOT_ID, uniq.split("-")[0], datas)
            if paste_url is None:
                output_filename = f"/tmp/output-{uuid4().hex}.txt"
                with open(output_filename, "w") as file:
                    data = html.escape(print_out)
                    data = data.replace("&quot;", "'")
                    file.write(data)
                await message.reply_document(
                    output_filename,
                    caption=f"<b>Elapsed: `{converted_time}.`</b>",
                )
                os.remove(output_filename)
                await reply_text.delete()
            else:
                inline = await ButtonUtils.send_inline_bot_result(
                    message,
                    message.chat.id,
                    bot.me.username,
                    f"inline_eval {uniq.split('-')[0]}",
                )
                if inline:
                    await reply_text.delete()
        else:
            datas = {"time": final_output}
            state.set(config.BOT_ID, uniq.split("-")[0], datas)
            inline = await ButtonUtils.send_inline_bot_result(
                message,
                message.chat.id,
                bot.me.username,
                f"inline_eval {uniq.split('-')[0]}",
            )
            if inline:
                await reply_text.delete()

    task_id = message.id
    _e_task = asyncio.create_task(eval_func())

    eval_tasks[task_id] = _e_task

    try:
        await _e_task
    except asyncio.CancelledError:
        await reply_text.edit_text("<b>Process Cancelled!</b>")
    finally:
        if task_id in eval_tasks:
            del eval_tasks[task_id]


async def send_large_output(message, output):
    with io.BytesIO(str.encode(str(output))) as out_file:
        out_file.name = "update.txt"
        await message.reply_document(document=out_file)


async def update_kode(client, message):
    out = subprocess.check_output(["git", "pull"]).decode("UTF-8")
    if "Already up to date." in str(out):
        return await message.reply(f"<pre>{out}</pre>")
    elif int(len(str(out))) > 4096:
        await send_large_output(message, out)
    else:
        await message.reply(f"<pre>{out}</pre>")
    os.execl(sys.executable, sys.executable, *sys.argv)


async def cb_gitpull2(client, message):
    user = message.from_user if message.from_user else message.sender_chat
    if user.id not in config.SUDO_OWNERS:
        return
    if message.command[0] == "update":
        return await update_kode(client, message)
    elif message.command[0] == "reboot":
        await message.reply(
            "<b>✅ Gunicorn stopped successfully. Trying to restart Userbot!!</b>"
        )
        os.execl(sys.executable, sys.executable, *sys.argv)


async def copymsg_bot(client, message):
    proses = await message.reply("<b>Please wait a minute...</b>")
    try:
        link = message.text.split()[1]
        if len(message.command) < 2:
            return await message.reply(
                f"<b><code>{message.text.split()[0]}</code> [link]</b>"
            )
        if link.startswith(("https", "t.me")):
            msg_id = int(link.split("/")[-1])
            if "t.me/c/" in link:
                chat = int("-100" + str(link.split("/")[-2]))
            else:
                chat = str(link.split("/")[-2])
            try:
                get_msg = await client.get_messages(chat, msg_id)
                try:
                    await get_msg.copy(message.chat.id)
                except Exception:
                    return await Tools.download_media(get_msg, client, proses, message)
            except Exception as er:
                return await message.reply(str(er))
        else:
            return await message.reply("Link tidak valid.")
    except Exception as er:
        logger.error(f"copy eror {str(er)}")
