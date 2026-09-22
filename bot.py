import os
import asyncio
import secrets
import requests
from aiohttp import web
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Render के Environment Variables से वैल्यू लोड होंगी ---
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

    # यूज़र डेटाबेस में चेक/ऐड करें
    user = users_col.find_one({"user_id": user_id})
    if not user:
        users_col.insert_one({"user_id": user_id, "tokens": 0})
        user = {"user_id": user_id, "tokens": 0}

    # 1. जब यूज़र शॉर्टनर सॉल्व करके वापस आएगा
    if args and args[0].startswith("verify_"):
        token_code = args[0]
        check_verify = verify_col.find_one({"token_code": token_code, "user_id": user_id, "used": False})
        
        if check_verify:
            verify_col.update_one({"token_code": token_code}, {"$set": {"used": True}})
            users_col.update_one({"user_id": user_id}, {"$inc": {"tokens": 3}})
            current_tokens = user.get("tokens", 0) + 3
            await update.message.reply_text(
                f"🎉 **verification completed!**\n\nआपको 3 टोकन मिल गए हैं।\nकुल टोकन: `{current_tokens}`\n\nअब आप चैनल से अपने 3 मंगा चैप्टर डाउनलोड कर सकते हैं।"
            )
            return
        else:
            await update.message.reply_text("❌ यह लिंक अमान्य है या पहले ही उपयोग हो चुका है।")
            return

    # 2. जब यूज़र चैनल से मंगा डाउनलोड करने आएगा (/start manga_...)
    if args and args[0].startswith("manga_"):
        file_key = args[0].replace("manga_", "")
        current_tokens = user.get("tokens", 0)

        # अगर टोकन 0 हैं -> शॉर्टनर लिंक दें
        if current_tokens <= 0:
            secret_code = "verify_" + secrets.token_hex(6)
            verify_col.insert_one({"token_code": secret_code, "user_id": user_id, "used": False})

            verify_link = f"https://t.me/{BOT_USERNAME}?start={secret_code}"
            short_url = get_short_link(verify_link)

            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 you get 3 tokens", url=short_url)]])
            await update.message.reply_text(
                "⚠️ **Your all token is finished!**\n\n"
                "aage ke token lene ke liye shortner solve karo:",
                reply_markup=btn
            )
            return

        # अगर टोकन हैं -> 1 टोकन काटें
        users_col.update_one({"user_id": user_id}, {"$inc": {"tokens": -1}})
        remaining = current_tokens - 1

        # डेटाबेस से फाइल भेजें
        manga = manga_col.find_one({"file_key": file_key})
        if manga and "telegram_file_id" in manga:
            await update.message.reply_document(
                document=manga["telegram_file_id"],
                caption=f"✅ **{manga.get('title', 'Manga Chapter')}**\n\nबाकी टोकन: `{remaining}`"
            )
        else:
            await update.message.reply_text(f"✅ manga file aa rahi hai...\n(बाकी टोकन: `{remaining}`)")
        return

    # साधारण /start भेजने पर
    tokens = user.get("tokens", 0)
    await update.message.reply_text(
        f"👋 नमस्ते {update.effective_user.first_name}!\n\n"
        f"आपके पास अभी `{tokens}` टोकन उपलब्ध हैं।\n"
        "चैनल में दिए गए मंगा डाउनलोड लिंक पर क्लिक करें।"
    )

# --- Render सर्वर को 24/7 जिंदा रखने के लिए ---
async def handle_ping(request):
    return web.Response(text="Manga Bot is running!")

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
