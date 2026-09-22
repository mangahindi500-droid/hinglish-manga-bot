import os
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Telegram Bot Token
TOKEN = "8815227985:AAENLEHZiMF4CMnNQY05hVDU06XTz7HLd9M"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("नमस्ते! बॉट Render पर सफलतापूर्वक लाइव हो चुका है।")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"आपने भेजा: {update.message.text}")

# Render को संतुष्ट रखने के लिए डमी वेब सर्वर
async def handle_ping(request):
    return web.Response(text="Bot is running fine on Render!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render खुद 'PORT' एनवायरनमेंट वेरिएबल देता है
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Dummy Web Server running on port {port}")

async def main():
    # 1. पहले वेब सर्वर चालू करें ताकि Render को पोर्ट तुरंत मिल जाए
    await start_web_server()

    # 2. टेलीग्राम बॉट शुरू करें
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("Bot polling started...")
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()

    # बॉट को 24/7 चालू रखने के लिए लूप
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
