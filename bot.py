import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("❤️ Create Profile", callback_data="create")],
        [InlineKeyboardButton("🔍 Find Match", callback_data="find")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to LoveConnect ❤️\n\nFind real love in Lagos & Nigeria.\n\nChoose an option below:",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "create":
        await query.message.reply_text("To create your profile, send:\n\nYour Name, Age, Location\n\nExample: Ada, 24, Lekki")
    elif query.data == "find":
        await query.message.reply_text("Finding matches near you... 🔍\n\nNo matches yet. Invite your friends to join @loveconnect_ng_bot")
    elif query.data == "about":
        await query.message.reply_text("LoveConnect is for real people in Lagos & Nigeria looking for serious love. ❤️")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
