import os
import asyncio
import secrets
import requests
from aiohttp import web
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Render Environment Variables ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
SHORTENER_API = os.environ.get("SHORTENER_API")
SHORTENER_URL = os.environ.get("SHORTENER_URL")
BOT_USERNAME = os.environ.get("BOT_USERNAME")

# --- Database Setup ---
client = MongoClient(MONGO_URI)
db = client["manga_bot_db"]
users_col = db["users"]
verify_col = db["verifications"]
manga_col = db["manga_files"]

# --- Shortener Function ---
def get_short_link(long_url):
    try:
        api_endpoint = f"{SHORTENER_URL}?api={SHORTENER_API}&url={long_url}"
        res = requests.get(api_endpoint).json()
        if res.get("status") == "success" or "shortenedUrl" in res:
            return res.get("shortenedUrl")
    except Exception as e:
        print(f"Shortener Error: {e}")
    return long_url

# --- Bot Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args

    # Check or register user in DB
    user = users_col.find_one({"user_id": user_id})
    if not user:
        users_col.insert_one({"user_id": user_id, "tokens": 0})
        user = {"user_id": user_id, "tokens": 0}

    # 1. Verification callback (/start verify_XYZ)
    if args and args[0].startswith("verify_"):
        token_code = args[0]
        check_verify = verify_col.find_one({"token_code": token_code, "user_id": user_id, "used": False})
        
        if check_verify:
            verify_col.update_one({"token_code": token_code}, {"$set": {"used": True}})
            users_col.update_one({"user_id": user_id}, {"$inc": {"tokens": 3}})
            current_tokens = user.get("tokens", 0) + 3
            await update.message.reply_text(
                f"🎉 **Verification Successful!**\n\n"
                f"Aapko **3 Tokens** credit kar diye gaye hain.\n"
                f"Total Balance: `{current_tokens}` Tokens\n\n"
                f"Ab aap channel se apne agle 3 manga chapters download kar sakte hain!"
            )
            return
        else:
            await update.message.reply_text("❌ Yeh link invalid hai ya pehle hi use ho chuka hai.")
            return

    # 2. Manga Download Request (/start manga_...)
    if args and args[0].startswith("manga_"):
        file_key = args[0].replace("manga_", "")
        current_tokens = user.get("tokens", 0)

        # Tokens finished (0 balance)
        if current_tokens <= 0:
            secret_code = "verify_" + secrets.token_hex(6)
            verify_col.insert_one({"token_code": secret_code, "user_id": user_id, "used": False})

            verify_link = f"https://t.me/{BOT_USERNAME}?start={secret_code}"
            short_url = get_short_link(verify_link)

            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 3 Tokens Paayein (Click Here)", url=short_url)]])
            await update.message.reply_text(
                "⚠️ **Aapke paas tokens khatam ho gaye hain!**\n\n"
                "Agle **3 Chapters** unlock karne ke liye niche diye gaye link ko complete karein aur 3 tokens paayein:",
                reply_markup=btn
            )
            return

        # Token available (> 0) -> Deduct 1 token
        users_col.update_one({"user_id": user_id}, {"$inc": {"tokens": -1}})
        remaining = current_tokens - 1

        # Send File from Database
        manga = manga_col.find_one({"file_key": file_key})
        if manga and "telegram_file_id" in manga:
            await update.message.reply_document(
                document=manga["telegram_file_id"],
                caption=f"✅ **{manga.get('title', 'Manga Chapter')}**\n\nRemaining Tokens: `{remaining}`"
            )
        else:
            await update.message.reply_text(f"✅ Aapka Manga Chapter process ho raha hai...\n(Remaining Tokens: `{remaining}`)")
        return

    # Normal /start
    tokens = user.get("tokens", 0)
    await update.message.reply_text(
        f"👋 Hello {update.effective_user.first_name}!\n\n"
        f"Aapke paas abhi `{tokens}` tokens available hain.\n\n"
        f"Channel me kisi bhi chapter ke **Download Now** link par click karein."
    )

# --- Render 24/7 Dummy Web Server ---
async def handle_ping(request):
    return web.Response(text="Manga Bot is running fine!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- Main App ---
async def main():
    await start_web_server()

    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))

    print("Bot polling started...")
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
