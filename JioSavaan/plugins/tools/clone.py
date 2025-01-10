import re
import logging
import asyncio
import importlib
from sys import argv


from pyrogram import idle, Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors.exceptions.bad_request_400 import AccessTokenExpired, AccessTokenInvalid

from JioSavaan.utils.database import get_assistant
from JioSavaan import app
from JioSavaan.misc import SUDOERS

from JioSavaan.utils import clonebotdb, ownerdb
from config import API_ID, API_HASH, LOGGER_ID
from config import BANNED_USERS


CLONES = set()

@app.on_message(filters.command(["clone"]) & filters.private & ~BANNED_USERS)
async def clone_command(client, message):
    await message.reply_text(
        "Choose an option below:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Clone", callback_data="provide_token"),
                    InlineKeyboardButton("Cloned Bots", callback_data="list_cloned_bots"),
                    InlineKeyboardButton("Remove Cloned Bot", callback_data="remove_cloned_bots")
                ]
            ]
        )
    )

@app.on_callback_query(filters.regex("provide_token"))
async def request_token(client, callback_query: CallbackQuery):
    await callback_query.message.edit_text("Please send me the bot token.")


@app.on_message(filters.command(["hclone"]) & filters.private & ~BANNED_USERS)
async def hclone_txt(client, message):
    userbot = await get_assistant(message.chat.id)
    if len(message.command) > 1:
        bot_token = message.text.split("/clone", 1)[1].strip()
        mi = await message.reply_text("Processing the bot token, please wait...")
        try:
            ai = Client(
                session_name=bot_token,
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=bot_token,
                plugins=dict(root="JioSavaan.cplugin")
            )
            await ai.start()
            bot = await ai.get_me()

        except (AccessTokenExpired, AccessTokenInvalid):
            await mi.edit_text("You have provided an invalid bot token. Please provide a valid bot token.")
            return
        except Exception as e:
            await mi.edit_text(f"An error occurred: {str(e)}")
            return

        await mi.edit_text("Cloning process started. Please wait...")
        try:
            await app.send_message(LOGGER_ID, f"**#New_Clones**\n\n**Bot:- @{bot.username}**")
            await userbot.send_message(bot.username, "/start")

            details = {
                "bot_id": bot.id,
                "is_bot": True,
                "user_id": message.from_user.id,
                "name": bot.first_name,
                "token": bot_token,
                "username": bot.username,
            }
            clonebotdb.insert_one(details)
            ownerdb.insert_one({"bot_id": bot.id, "owner_id": message.from_user.id, "original_bot": message.bot.id})
            CLONES.add(bot.id)
            await mi.edit_text(
                f"Bot @{bot.username} has been successfully cloned and started ✅.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("Remove Clone", callback_data=f"remove_clone_{bot.id}"),InlineKeyboardButton("Manage Clones", callback_data=f"list_user_cloned_bots_{message.from_user.id}")
                        ]
                    ]
                )
            )
            await client.send_message(message.from_user.id, f"Your bot @{bot.username} has been successfully cloned and started! ✅")
        except BaseException as e:
            logging.exception("Error while cloning bot.")
            await mi.edit_text(f"⚠️ <b>ERROR:</b>\n\n<code>{e}</code>\n\n*Please forward this message to @nobi_bots for assistance.*")
    else:
        await message.reply_text("Invalid bot token format. Please provide a valid bot token from @BotFather.")

@app.on_callback_query(filters.regex("list_cloned_bots"))
async def list_cloned_bots(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    cloned_bots = clonebotdb.find({"user_id": user_id})
    cloned_bots_list = [bot for bot in cloned_bots]
    if not cloned_bots_list:
        await callback_query.message.edit_text("You haven't cloned any bots yet.")
        return

    text = "Your cloned bots:\n\n"
    buttons = []

    for bot in cloned_bots_list:
        text += f"@{bot['username']}\n"
        buttons.append([InlineKeyboardButton(f"Remove @{bot['username']}", callback_data=f"remove_clone_{bot['bot_id']}")])

    if user_id in SUDOERS:
        all_bots = clonebotdb.find()
        admin_text = "\n\nAll cloned bots:\n\n"
        admin_buttons = []

        for bot in all_bots:
            admin_text += f"@{bot['username']} (User ID: {bot['user_id']})\n"
            admin_buttons.append([InlineKeyboardButton(f"Remove @{bot['username']}", callback_data=f"remove_clone_{bot['bot_id']}")])

        text += admin_text
        buttons.extend(admin_buttons)

    await callback_query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex(r"remove_clone_\d+"))
async def remove_clone(client, callback_query: CallbackQuery):
    bot_id = int(callback_query.data.split("_")[2])
    cloned_bot = clonebotdb.find_one({"bot_id": bot_id})
    if cloned_bot:
        clonebotdb.delete_one({"bot_id": bot_id})
        ownerdb.delete_one({"bot_id": bot_id})
        CLONES.remove(bot_id)
        await callback_query.message.edit_text(f"Bot @{cloned_bot['username']} has been successfully removed.")
        await client.send_message(cloned_bot['user_id'], f"Your bot @{cloned_bot['username']} has been successfully removed.")
    else:
        await callback_query.message.edit_text("Bot not found in the cloned list.")

@app.on_callback_query(filters.regex(r"remove_all_clones_\d+"))
async def remove_all_clones(client, callback_query: CallbackQuery):
    user_id = int(callback_query.data.split("_")[3])
    cloned_bots = clonebotdb.find({"user_id": user_id})
    if not cloned_bots:
        await callback_query.message.edit_text("No cloned bots found for this user.")
        return

    for bot in cloned_bots:
        clonebotdb.delete_one({"bot_id": bot["bot_id"]})
        ownerdb.delete_one({"bot_id": bot["bot_id"]})
        CLONES.discard(bot["bot_id"])

    await callback_query.message.edit_text("All your cloned bots have been successfully removed.")
    await client.send_message(user_id, "All your cloned bots have been successfully removed.")


async def restart_bots():
    global CLONES
    try:
        logging.info("Restarting all cloned bots........")
        bots = clonebotdb.find()
        async for bot in bots:
            bot_token = bot["token"]
            ai = Client(
                f"{bot_token}",
                API_ID,
                API_HASH,
                bot_token=bot_token,
                plugins=dict(root="JioSavaan.cplugin"),
            )
            await ai.start()
            bot = await ai.get_me()
            if bot.id not in CLONES:
                try:
                    CLONES.add(bot.id)
                except Exception:
                    pass
    except Exception as e:
        logging.exception("Error while restarting bots.")