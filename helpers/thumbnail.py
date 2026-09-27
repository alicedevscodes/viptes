import os

import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from database import state
from logs import logger

from .buttons import ButtonUtils
from .tools import Tools


def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage


def truncate(text):
    list = text.split(" ")
    text1 = ""
    text2 = ""
    for i in list:
        if len(text1) + len(i) < 30:
            text1 += " " + i
        elif len(text2) + len(i) < 30:
            text2 += " " + i

    text1 = text1.strip()
    text2 = text2.strip()
    return [text1, text2]


def crop_center_circle(img, output_size, border, crop_scale=1.5):
    half_the_width = img.size[0] / 2
    half_the_height = img.size[1] / 2
    larger_size = int(output_size * crop_scale)
    img = img.crop(
        (
            half_the_width - larger_size / 2,
            half_the_height - larger_size / 2,
            half_the_width + larger_size / 2,
            half_the_height + larger_size / 2,
        )
    )

    img = img.resize((output_size - 2 * border, output_size - 2 * border))

    final_img = Image.new("RGBA", (output_size, output_size), "white")

    mask_main = Image.new("L", (output_size - 2 * border, output_size - 2 * border), 0)
    draw_main = ImageDraw.Draw(mask_main)
    draw_main.ellipse(
        (0, 0, output_size - 2 * border, output_size - 2 * border), fill=255
    )

    final_img.paste(img, (border, border), mask_main)

    mask_border = Image.new("L", (output_size, output_size), 0)
    draw_border = ImageDraw.Draw(mask_border)
    draw_border.ellipse((0, 0, output_size, output_size), fill=255)

    result = Image.composite(
        final_img, Image.new("RGBA", final_img.size, (0, 0, 0, 0)), mask_border
    )

    return result


async def gen_qthumb(client, videoid):
    if os.path.isfile(f"storage/cache/{videoid}_v4.png"):
        return f"storage/cache/{videoid}_v4.png"
    data = state.get(client.me.id, "GEN_THUMB")
    title = data["title"]
    duration = data["duration"]
    logger.info(f"Duration: {duration}")
    views = data["views"]
    thumbnail = data["thumbnail"]
    logger.info(f"Url thumbnail: {thumbnail}")
    channel = data["channel"]
    valid, _ = ButtonUtils.cek_tg(thumbnail)
    if valid:
        path = f"storage/cache/thumb{videoid}.png"
        await Tools.bash(f"wget {thumbnail} -O {path}")
    else:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(
                        f"storage/cache/thumb{videoid}.png", mode="wb"
                    )
                    await f.write(await resp.read())
                    await f.close()

    youtube = Image.open(f"storage/cache/thumb{videoid}.png")
    image1 = changeImageSize(1280, 720, youtube)
    image2 = image1.convert("RGBA")
    background = image2.filter(filter=ImageFilter.BoxBlur(20))
    enhancer = ImageEnhance.Brightness(background)
    background = enhancer.enhance(0.6)
    draw = ImageDraw.Draw(background)
    arial = ImageFont.truetype("storage/cache/font2.ttf", 30)
    ImageFont.truetype("storage/cache/font.ttf", 30)
    title_font = ImageFont.truetype("storage/cache/font3.ttf", 45)

    circle_thumbnail = crop_center_circle(youtube, 400, 20)
    circle_thumbnail = circle_thumbnail.resize((400, 400))
    circle_position = (120, 160)
    background.paste(circle_thumbnail, circle_position, circle_thumbnail)

    text_x_position = 565

    title1 = truncate(title)
    draw.text((text_x_position, 180), title1[0], fill=(255, 255, 255), font=title_font)
    draw.text((text_x_position, 230), title1[1], fill=(255, 255, 255), font=title_font)
    draw.text(
        (text_x_position, 320),
        f"{channel}  |  {views[:23]}",
        (255, 255, 255),
        font=arial,
    )

    line_length = 580

    red_length = int(line_length * 0.6)
    line_length - red_length

    start_point_red = (text_x_position, 380)
    end_point_red = (text_x_position + red_length, 380)
    draw.line([start_point_red, end_point_red], fill="red", width=9)

    start_point_white = (text_x_position + red_length, 380)
    end_point_white = (text_x_position + line_length, 380)
    draw.line([start_point_white, end_point_white], fill="white", width=8)

    circle_radius = 10
    circle_position = (end_point_red[0], end_point_red[1])
    draw.ellipse(
        [
            circle_position[0] - circle_radius,
            circle_position[1] - circle_radius,
            circle_position[0] + circle_radius,
            circle_position[1] + circle_radius,
        ],
        fill="red",
    )
    draw.text((text_x_position, 400), "00:00", (255, 255, 255), font=arial)
    draw.text((1080, 400), duration, (255, 255, 255), font=arial)

    play_icons = Image.open("storage/cache/play_icons.png")
    play_icons = play_icons.resize((580, 62))
    background.paste(play_icons, (text_x_position, 450), play_icons)

    try:
        os.remove(f"storage/cache/thumb{videoid}.png")
    except:
        pass
    background.save(f"storage/cache/{videoid}_v4.png")
    return f"storage/cache/{videoid}_v4.png"
