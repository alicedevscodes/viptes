from command import cancelpay_cmd, qris_cmd
from helpers import CMD


@CMD.UBOT("pay|qris")
async def _(client, message):
    return await qris_cmd(client, message)


@CMD.UBOT("cancelpay")
async def _(client, message):
    return await cancelpay_cmd(client, message)
