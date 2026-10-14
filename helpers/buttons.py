import re
import traceback
from math import ceil
from typing import List, Optional, Tuple
from uuid import uuid4

from pyrogram.helpers import ikb, kb
from pyrogram.enums import ButtonStyle
from pyrogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                            WebAppInfo)

from database import dB, state
from logs import logger

COLUMN_SIZE = 4  # Controls the button number of height
NUM_COLUMNS = 2  # Controls the button number of width


class EqInlineKeyboardButton(InlineKeyboardButton):
    def __eq__(self, other):
        return self.text == other.text

    def __lt__(self, other):
        return self.text < other.text

    def __gt__(self, other):
        return self.text > other.text


def paginate_modules(page_n, module_dict, prefix, is_bot=False):
    modules = sorted(
        [
            EqInlineKeyboardButton(
                x["module"].__MODULES__,
                callback_data="{}_module({},{})".format(
                    prefix, x["module"].__MODULES__.lower(), page_n
                ),
            )
            for x in module_dict.values()
            if hasattr(x["module"], "__MODULES__")
        ]
    )
    pairs = [modules[i : i + NUM_COLUMNS] for i in range(0, len(modules), NUM_COLUMNS)]

    max_num_pages = ceil(len(pairs) / COLUMN_SIZE) if len(pairs) > 0 else 1
    modulo_page = page_n % max_num_pages

    if is_bot:
        if len(pairs) > COLUMN_SIZE:
            pairs = pairs[
                modulo_page * COLUMN_SIZE : COLUMN_SIZE * (modulo_page + 1)
            ] + [
                (
                    EqInlineKeyboardButton(
                        "❮",
                        callback_data="{}_prev({})".format(
                            prefix,
                            modulo_page - 1 if modulo_page > 0 else max_num_pages - 1,
                        ),
                    ),
                    EqInlineKeyboardButton("x", callback_data="buttonclose"),
                    EqInlineKeyboardButton(
                        "❯",
                        callback_data="{}_next({})".format(prefix, modulo_page + 1),
                    ),
                )
            ]
        else:
            pairs.append(
                [
                    EqInlineKeyboardButton(
                        "🔙 Back",
                        callback_data="{}_help_back({})",
                    ),
                ]
            )
    else:
        if len(pairs) > COLUMN_SIZE:
            pairs = pairs[
                modulo_page * COLUMN_SIZE : COLUMN_SIZE * (modulo_page + 1)
            ] + [
                (
                    EqInlineKeyboardButton(
                        "❮",
                        callback_data="{}_prev({})".format(
                            prefix,
                            modulo_page - 1 if modulo_page > 0 else max_num_pages - 1,
                        ),
                    ),
                    EqInlineKeyboardButton("x", callback_data="close help"),
                    EqInlineKeyboardButton(
                        "❯",
                        callback_data="{}_next({})".format(prefix, modulo_page + 1),
                    ),
                )
            ]
        else:
            pairs.append(
                [
                    EqInlineKeyboardButton(
                        "🔙 Back",
                        callback_data="{}_help_back({})",
                    ),
                ]
            )

    return pairs


class ButtonUtils:
    # Compile regex patterns for better performance
    URL_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?[a-zA-Z0-9.-]+(?:\.[a-zA-Z]{2,})+(?:[/?]\S+)?|tg://\S+"
    )
    BUTTON_PATTERN = re.compile(r"\[(.*?)\|(.*?)\]")
    FORMAT_TAGS = {
        "<b>": "**",
        "<i>": "__",
        "<strike>": "~~",
        "<spoiler>": "||",
        "<u>": "--",
    }

    @staticmethod
    def is_url(text: str) -> bool:
        """Check if text is a URL."""
        # return bool(ButtonUtils.URL_PATTERN.match(text))
        return bool(re.search(ButtonUtils.URL_PATTERN, text))

    @staticmethod
    def is_number(text: str) -> bool:
        """Check if text is a number."""
        return text.isdigit()

    @staticmethod
    def is_copy(text: str) -> bool:
        pattern = r"copy:"

        return bool(re.search(pattern, text))

    @staticmethod
    def is_alert(text: str) -> bool:
        pattern = r"alert:"

        return bool(re.search(pattern, text))

    @staticmethod
    def is_web(text: str) -> bool:
        pattern = r"web:"

        return bool(re.search(pattern, text))

    @staticmethod
    def cek_tg(text):
        tg_pattern = r"https?:\/\/files\.catbox\.moe\/\S+"
        match = re.search(tg_pattern, text)

        if match:
            tg_link = match.group(0)
            non_tg_text = text.replace(tg_link, "").strip()
            return tg_link, non_tg_text
        else:
            return (None, text)

    @staticmethod
    def parse_msg_buttons(texts: str) -> Tuple[str, List[List]]:
        btn = []
        for z in ButtonUtils.BUTTON_PATTERN.findall(texts):
            text, url = z
            urls = url.split("|")
            url = urls[0]
            if len(urls) > 1:
                btn[-1].append([text, url])
            else:
                btn.append([[text, url]])

        txt = texts
        for z in re.findall(r"\[.+?\|.+?\]", texts):
            txt = txt.replace(z, "")

        return txt.strip(), btn

    @staticmethod
    async def create_button(
        text: str, data: str, with_suffix: str = ""
    ) -> InlineKeyboardButton:
        """Create an InlineKeyboardButton based on data type."""
        data = data.strip()
        if ButtonUtils.is_url(data):
            return InlineKeyboardButton(text=text, url=data)
        elif ButtonUtils.is_number(data):
            return InlineKeyboardButton(text=text, user_id=int(data))
        elif ButtonUtils.is_copy(data):
            return InlineKeyboardButton(text=text, copy_text=data.replace("copy:", ""))
        elif ButtonUtils.is_alert(data):
            alert_text = data.replace("alert:", "")
            uniq = str(uuid4().int)[:8]
            await dB.set_var(int(uniq), int(uniq), alert_text)
            cb_data = f"alertcb_{int(uniq)}"
            return InlineKeyboardButton(text=text, callback_data=cb_data)
        elif ButtonUtils.is_web(data):
            url = data.replace("web:", "")
            logger.info(f"Type data:{url} ")
            return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))
        return InlineKeyboardButton(
            text=text, callback_data=f"{data}_{with_suffix}" if with_suffix else data
        )

    @staticmethod
    async def create_inline_keyboard(
        buttons: List[List], suffix: str = ""
    ) -> InlineKeyboardMarkup:
        """Create InlineKeyboardMarkup from button data."""
        keyboard = []
        for row in buttons:
            if len(row) > 1:
                keyboard.append(
                    [
                        await ButtonUtils.create_button(text, data, suffix)
                        for text, data in row
                    ]
                )
            else:
                text, data = row[0]
                keyboard.append([await ButtonUtils.create_button(text, data, suffix)])
        return InlineKeyboardMarkup(keyboard)

    """Pre-defined keyboard templates for Pyrogram."""

    @staticmethod
    def start_menu(is_admin: bool = False) -> kb:
        """Generate start menu keyboard."""
        common_buttons = [
        [
          (("Beli Seblak Bang"), ButtonStyle.PRIMARY, "5373052667671093676"),
        ],
        [
          (("Tombol Custom DLL"), ButtonStyle.DANGER, "6240210026477130678"),
        ],
          
    ]

        if is_admin:
            common_buttons.extend(
                [
                    ["© Alicecodes"],
                ]
            )
        else:
            common_buttons.extend([["©️ @devspaybot"]])

        return kb(common_buttons, resize_keyboard=True, one_time_keyboard=True)

    @staticmethod
    def userbot(user_id, count):
        button = ikb(
            [
                [
                    (
                        "Delete User",
                        f"del_ubot {int(user_id)}",
                    ),
                    (
                        "Check Phone",
                        f"get_phone {int(count)}",
                    ),
                ],
                [
                    (
                        "Check Expired",
                        f"cek_masa_aktif {int(user_id)}",
                    )
                ],
                [
                    (
                        "Get Otp",
                        f"get_otp {int(count)}",
                    ),
                    (
                        "Get V2L",
                        f"get_faktor {int(count)}",
                    ),
                ],
                [
                    (
                        "Delete Account",
                        f"ub_deak {int(count)}",
                    )
                ],
                [
                    ("❮", f"prev_ub {int(count)}"),
                    ("Close", "buttonclose"),
                    ("❯", f"next_ub {int(count)}"),
                ],
            ]
        )
        return button

    @staticmethod
    def fake_userbot(user_id, count):
        button = ikb(
            [
                [
                    (
                        "Delete User",
                        f"del_ubot {int(user_id)}",
                    ),
                ],
                [
                    (
                        "Check Expired",
                        f"cek_masa_aktif {int(user_id)}",
                    )
                ],
                [
                    ("❮", f"fakeprev_ub {int(count)}"),
                    ("Close", "buttonclose"),
                    ("❯", f"fakenext_ub {int(count)}"),
                ],
            ]
        )
        return button

    @staticmethod
    def deak(user_id, count):
        button = ikb(
            [[("⬅️", f"prev_ub {int(count)}"), ("Approve", f"deak_akun {int(count)}")]]
        )
        return button

    @staticmethod
    async def generate_inline_query(message, chat_id, bot_username, query):
        try:
            client = message._client
            results = await client.get_inline_bot_results(bot_username, query)
            if results and results.results:
                return {
                    "query_id": results.query_id,
                    "result_id": results.results[0].id,
                    "results": results.results,
                    "query": query,
                }
            return None
        except Exception:
            return None

    @staticmethod
    async def send_inline_bot_result(
        message,
        chat_id,
        bot_username,
        query,
        reply_to_message_id: Optional[int] = None,
    ) -> bool:
        """
        Send inline bot result to chat.

        Args:
            client: Pyrogram Client instance
            message: Original message to reply to
            bot_username: Username of the bot to query
            query: Query string to send to the bot
            reply_to_message_id: Optional message ID to reply to

        Returns:
            Boolean indicating success/failure
        """
        client = message._client
        try:
            query_results = await ButtonUtils.generate_inline_query(
                message, chat_id, bot_username, query
            )

            if not query_results:
                return False

            data = await client.send_inline_bot_result(
                chat_id,
                query_results["query_id"],
                query_results["result_id"],
                reply_to_message_id=reply_to_message_id,
            )
            # logger.warning(f"line 273 {data}")
            inline_id = {
                "chat": chat_id,
                "_id": data.updates[0].id,
                "me": client.me.id,
                "idm": id(message),
            }
            state.set(query, query, inline_id)
            return True

        except Exception:
            logger.error(f"Error in send_inline_bot_result: {traceback.format_exc()}")
            return False

    @staticmethod
    def plus_minus(bulan, harga, plan):
        button = ikb(
            [
                [
                    (" Ya saya ingin membeli", f"tambah {bulan} {harga} {plan}", ButtonStyle.PRIMARY, "5373052667671093676"),
                ],
                [(" Konfirmasi", f"confirm {harga} {plan}", ButtonStyle.SUCCESS, "6296367896398399651")],
                [(" Batal", "buttonclose", ButtonStyle.DANGER, "5260293700088511294")],
            ]
        )
        return button

    @staticmethod
    def chose_plan():
        button = ikb(
            [
                [
                    (
                      ((" Seblak Pedas"), 
                     f"planusers basic", ButtonStyle.DANGER, "5458908492687497206")
                    ), 
                    (
                      ((" Seblak Non Pedas"),
                     f"planusers is_pro", ButtonStyle.PRIMARY, "5258397811329739167")
                    ),
                ],
                [
                    (
                      ((" beli nokos"),
                     f"planusers nokos", ButtonStyle.PRIMARY, "5258397811329739167")
                    ),
                ],
                [(" Batal", "buttonclose", ButtonStyle.DANGER, "5260293700088511294")],
            ]
        )
        return button

    @staticmethod
    def create_font_keyboard(font_list, get_id, current_batch):
        keyboard = []
        for font_dict in font_list:
            for key, value in font_dict.items():
                keyboard.append(
                    InlineKeyboardButton(
                        key, callback_data=f"get_font {get_id} {value}"
                    )
                )

        rows = [keyboard[i : i + 2] for i in range(0, len(keyboard), 2)]

        while len(rows) < 3:
            rows.append([])

        rows.append(
            [
                InlineKeyboardButton(
                    "⬅️", callback_data=f"prev_font {get_id} {current_batch}"
                ),
                InlineKeyboardButton("❌", callback_data=f"close inline_font {get_id}"),
                InlineKeyboardButton(
                    "➡️", callback_data=f"next_font {get_id} {current_batch}"
                ),
            ]
        )
        return rows

    @staticmethod
    def create_buttons_textpro(font_list, get_id, current_batch):
        keyboard = []
        for font_dict in font_list:
            for key, value in font_dict.items():
                keyboard.append(
                    InlineKeyboardButton(key, callback_data=f"genpro {get_id} {value}")
                )

        rows = [keyboard[i : i + 2] for i in range(0, len(keyboard), 2)]

        while len(rows) < 3:
            rows.append([])

        rows.append(
            [
                InlineKeyboardButton(
                    "⬅️", callback_data=f"prev_textpro {get_id} {current_batch}"
                ),
                InlineKeyboardButton(
                    "❌", callback_data=f"close inline_textpro {get_id}"
                ),
                InlineKeyboardButton(
                    "➡️", callback_data=f"next_textpro {get_id} {current_batch}"
                ),
            ]
        )
        return rows
