from clients import navy
from command import (add_prem_user, add_pro_user, add_seller, cb_evalusi,
                     cb_gitpull2, cb_shell, plugins_cmd, seller_cmd, set_plan,
                     un_prem_user, un_seller)
from helpers import CMD


@CMD.UBOT("addprem")
@CMD.SELLER_AND_GC
async def _(client, message):
    return await add_prem_user(client, message)


@CMD.UBOT("addpro")
@CMD.SELLER_AND_GC
async def _(client, message):
    return await add_pro_user(client, message)


@CMD.UBOT("set_plan")
@CMD.SELLER_AND_GC
async def _(client, message):
    return await set_plan(client, message)


@CMD.UBOT("unprem")
@CMD.SELLER_AND_GC
async def _(client, message):
    return await un_prem_user(client, message)


@CMD.UBOT("addseller")
@CMD.FAKE_NLX
async def _(client, message):
    return await add_seller(client, message)


@CMD.UBOT("unseller")
@CMD.FAKE_NLX
async def _(client, message):
    return await un_seller(client, message)


@CMD.UBOT("shell|sh")
@CMD.NLX
async def _(client: navy, message):
    return await cb_shell(client, message)


@CMD.UBOT("eval|ev|e")
@CMD.NLX
@CMD.DEV_CMD("ceval")
async def _(client: navy, message):
    return await cb_evalusi(client, message)


@CMD.UBOT("reboot|update")
@CMD.FAKE_NLX
async def _(client: navy, message):
    return await cb_gitpull2(client, message)


@CMD.UBOT("seller")
@CMD.FAKE_NLX
async def _(client, message):
    return await seller_cmd(client, message)


@CMD.UBOT("loadplugins|unloadplugins|listplugins")
@CMD.NLX
async def _(client, message):
    return await plugins_cmd(client, message)
