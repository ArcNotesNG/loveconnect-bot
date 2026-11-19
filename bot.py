import sqlite3, logging, datetime, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ============ CONFIG - SAFE FOR GITHUB ============
# Real token goes in Render > Environment Variables, NOT here
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
DB_FILE = "loveconnect.db"

WEEKLY_LINK = "https://paystack.shop/pay/loveconnect-weekly"
MONTHLY_LINK = "https://paystack.shop/pay/loveconnect-monthly"
THREE_MONTHS_LINK = "https://paystack.shop/pay/loveconnect-3months"

PLANS = {
    "weekly": {"price": 1500, "days": 7, "label": "Weekly - ₦1,500", "link": WEEKLY_LINK},
    "monthly": {"price": 3500, "days": 30, "label": "Monthly - ₦3,500", "link": MONTHLY_LINK},
    "3months": {"price": 8000, "days": 90, "label": "3 Months - ₦8,000", "link": THREE_MONTHS_LINK},
}

NAME, AGE, GENDER, LOCATION, BIO, PHOTO = range(6)
logging.basicConfig(level=logging.INFO)

# ============ DATABASE ============
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT, name TEXT, age INTEGER, gender TEXT,
        location TEXT, bio TEXT, photo_id TEXT,
        is_premium INTEGER DEFAULT 0, premium_until TEXT,
        created_at TEXT, is_banned INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, plan TEXT, amount INTEGER,
        receipt_file_id TEXT, status TEXT DEFAULT 'pending',
        created_at TEXT, approved_by INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS seen (
        viewer_id INTEGER, viewed_id INTEGER, UNIQUE(viewer_id, viewed_id)
    )""")
    c.commit(); c.close()

def get_user(uid):
    c = db(); r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone(); c.close()
    return r

def is_premium(uid):
    u = get_user(uid)
    if not u or not u["is_premium"]: return False
    if u["premium_until"]:
        until = datetime.datetime.fromisoformat(u["premium_until"])
        if datetime.datetime.now() > until:
            c = db(); c.execute("UPDATE users SET is_premium=0 WHERE user_id=?", (uid,)); c.commit(); c.close()
            return False
        return True
    return False

# ============ START & PROFILE ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    if u:
        return await show_menu(update, context, f"Welcome back, {u['name']} 💖")
    await update.message.reply_text("Welcome to *LoveConnect* 💖\nNigeria's Real Dating Bot.\n\nLet's create your profile.\n\nWhat is your name?")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("How old are you? (e.g 24)")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
        if age < 18 or age > 70:
            await update.message.reply_text("You must be 18-70. Try again:")
            return AGE
    except:
        await update.message.reply_text("Send number only, e.g 24")
        return AGE
    context.user_data["age"] = age
    kb = [[InlineKeyboardButton("👨 Male", callback_data="gender_Male"), InlineKeyboardButton("👩 Female", callback_data="gender_Female")]]
    await update.message.reply_text("Are you Male or Female?", reply_markup=InlineKeyboardMarkup(kb))
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["gender"] = q.data.split("_")[1]
    kb = [
        [InlineKeyboardButton("Lagos - Lekki", callback_data="loc_Lekki"), InlineKeyboardButton("Lagos - Ikeja", callback_data="loc_Ikeja")],
        [InlineKeyboardButton("Lagos - Yaba", callback_data="loc_Yaba"), InlineKeyboardButton("Lagos - Surulere", callback_data="loc_Surulere")],
        [InlineKeyboardButton("Abuja", callback_data="loc_Abuja"), InlineKeyboardButton("Port Harcourt", callback_data="loc_PH")],
        [InlineKeyboardButton("Other", callback_data="loc_Other")],
    ]
    await q.edit_message_text("Where are you based?", reply_markup=InlineKeyboardMarkup(kb))
    return LOCATION

async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["location"] = q.data.split("_",1)[1]
    await q.edit_message_text("Write a short bio about yourself (e.g I love music, gym, and good food).")
    return BIO

async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bio"] = update.message.text.strip()[:200]
    await update.message.reply_text("Send one clear photo of yourself.")
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Please send a photo.")
        return PHOTO
    photo_id = update.message.photo[-1].file_id
    u = update.effective_user
    c = db()
    c.execute("INSERT OR REPLACE INTO users (user_id, username, name, age, gender, location, bio, photo_id, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (u.id, u.username, context.user_data["name"], context.user_data["age"], context.user_data["gender"], context.user_data["location"], context.user_data["bio"], photo_id, datetime.datetime.now().isoformat()))
    c.commit(); c.close()
    await update.message.reply_text("✅ Profile created! Let's find your match.")
    await show_menu(update, context, "Profile ready 💖")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Send /start to try again.")
    return ConversationHandler.END

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="Main Menu"):
    kb = [
        [InlineKeyboardButton("💖 Find Match", callback_data="find_match")],
        [InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],
        [InlineKeyboardButton("🔓 Unlock / Premium", callback_data="unlock_menu")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ]
    markup = InlineKeyboardMarkup(kb)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)

# ============ MATCHING ============
async def find_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    me = get_user(uid)
    if not me:
        await q.edit_message_text("Please send /start to create profile first.")
        return
    target_gender = "Female" if me["gender"] == "Male" else "Male"
    c = db()
    row = c.execute("""SELECT * FROM users WHERE gender=? AND user_id != ? AND is_banned=0
        AND user_id NOT IN (SELECT viewed_id FROM seen WHERE viewer_id=?)
        ORDER BY RANDOM() LIMIT 1""", (target_gender, uid, uid)).fetchone()
    if not row:
        c.execute("DELETE FROM seen WHERE viewer_id=?", (uid,)); c.commit()
        await q.edit_message_text("No new matches now. Try again later.")
        c.close(); return
    c.execute("INSERT OR IGNORE INTO seen VALUES (?,?)", (uid, row["user_id"])); c.commit(); c.close()
    context.user_data["current_match_id"] = row["user_id"]
    premium = is_premium(uid)
    username_display = f"@{row['username']}" if (premium and row["username"]) else "🔒 ******* (Locked - Unlock to see)"
    kb = [
        [InlineKeyboardButton("🔓 Unlock Match", callback_data="unlock_menu")],
        [InlineKeyboardButton("❤️ Like", callback_data="like_match"), InlineKeyboardButton("⏭️ Next", callback_data="find_match")],
    ]
    await context.bot.send_photo(q.message.chat_id, row["photo_id"],
        caption=f"💖 *{row['name']}, {row['age']}*\n📍 {row['location']}\n📝 {row['bio']}\n\nUsername: {username_display}",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def like_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    match_id = context.user_data.get("current_match_id")
    if not match_id:
        await q.edit_message_text("Find a match first."); return
    await context.bot.send_message(match_id, "💖 Someone liked your profile! Open LoveConnect to see who.")
    await q.edit_message_text("❤️ Like sent!")

# ============ PREMIUM / PAYMENT ============
async def unlock_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if is_premium(uid):
        u = get_user(uid)
        await q.edit_message_text(f"✅ You are Premium until {u['premium_until'][:10]}.\nYour matches are already unlocked!")
        return
    kb = [
        [InlineKeyboardButton("💳 Weekly - ₦1,500 (7 days)", url=PLANS["weekly"]["link"])],
        [InlineKeyboardButton("💳 Monthly - ₦3,500 (30 days) ⭐", url=PLANS["monthly"]["link"])],
        [InlineKeyboardButton("💳 3 Months - ₦8,000 (90 days) 🔥", url=PLANS["3months"]["link"])],
        [InlineKeyboardButton("✅ I Have Paid", callback_data="i_have_paid")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_home")],
    ]
    await q.edit_message_text(
        "🔓 *Unlock Match*\n\nChoose plan:\n\n*Weekly ₦1,500* - 7 days\n*Monthly ₦3,500* - 30 days - Most Popular\n*3 Months ₦8,000* - 90 days - Best Value\n\n1. Tap Pay (Paystack)\n2. Screenshot receipt\n3. Tap I Have Paid & send receipt",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def i_have_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [[InlineKeyboardButton(v["label"], callback_data=f"paid_{k}")] for k,v in PLANS.items()]
    await q.edit_message_text("Which plan did you pay for?", reply_markup=InlineKeyboardMarkup(kb))

async def paid_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    plan = q.data.replace("paid_", "")
    context.user_data["pending_plan"] = plan
    context.user_data["waiting_receipt"] = True
    await q.edit_message_text(f"You selected *{PLANS[plan]['label']}*.\n\nNow send your Paystack receipt screenshot as PHOTO.\n\n⚠️ Fake receipts = permanent ban.", parse_mode="Markdown")

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_receipt"): return
    if not update.message.photo:
        await update.message.reply_text("Send receipt as PHOTO, not file."); return
    uid = update.effective_user.id
    plan = context.user_data.get("pending_plan", "weekly")
    context.user_data["waiting_receipt"] = False
    file_id = update.message.photo[-1].file_id
    c = db()
    c.execute("INSERT INTO payments (user_id, plan, amount, receipt_file_id, created_at) VALUES (?,?,?,?,?)",
        (uid, plan, PLANS[plan]["price"], file_id, datetime.datetime.now().isoformat()))
    c.commit(); c.close()
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{plan}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]]
    await context.bot.send_message(ADMIN_ID, f"💰 *NEW PAYMENT*\nUser: @{update.effective_user.username} ({uid})\nPlan: {PLANS[plan]['label']} - ₦{PLANS[plan]['price']}\n\nCheck receipt & Paystack dashboard before approving!", parse_mode="Markdown")
    await context.bot.send_photo(ADMIN_ID, file_id, caption=f"Receipt from {uid} - {plan}", reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("✅ Receipt received. Admin will verify on Paystack and approve.")

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("Not admin."); return
    parts = q.data.split("_")
    action = parts[0]; uid = int(parts[1])
    if action == "approve":
        plan = parts[2]
        days = PLANS[plan]["days"]
        until = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
        c = db()
        c.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?", (until, uid))
        c.execute("UPDATE payments SET status='approved', approved_by=? WHERE user_id=? AND status='pending'", (ADMIN_ID, uid))
        c.commit(); c.close()
        await context.bot.send_message(uid, f"🎉 *Payment Approved!*\n\nYour {PLANS[plan]['label']} is ACTIVE until {until[:10]}.\n\nNow go to Find Match - all usernames are unlocked! 💖", parse_mode="Markdown")
        await q.edit_message_text(f"✅ Approved {uid} for {plan}")
    else:
        c = db(); c.execute("UPDATE payments SET status='rejected' WHERE user_id=? AND status='pending'", (uid,)); c.commit(); c.close()
        await context.bot.send_message(uid, "❌ Payment not confirmed. Please send correct receipt or contact support.")
        await q.edit_message_text(f"❌ Rejected {uid}")

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    u = get_user(q.from_user.id)
    if not u: await q.edit_message_text("Send /start to create profile."); return
    status = f"Premium until {u['premium_until'][:10]} ✅" if is_premium(q.from_user.id) else "Free (Locked) 🔒"
    await q.edit_message_text(f"👤 *{u['name']}, {u['age']}*\n📍 {u['location']}\n📝 {u['bio']}\nStatus: {status}", parse_mode="Markdown")

async def back_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await show_menu(update, context, "Welcome back 💖")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
                GENDER: [CallbackQueryHandler(get_gender, pattern="^gender_")],
                LOCATION: [CallbackQueryHandler(get_location, pattern="^loc_")],
                BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
                PHOTO: [MessageHandler(filters.PHOTO, get_photo)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(find_match, pattern="^find_match$"))
    app.add_handler(CallbackQueryHandler(like_match, pattern="^like_match$"))
    app.add_handler(CallbackQueryHandler(unlock_menu, pattern="^unlock_menu$"))
    app.add_handler(CallbackQueryHandler(i_have_paid, pattern="^i_have_paid$"))
    app.add_handler(CallbackQueryHandler(paid_selected, pattern="^paid_"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(my_profile, pattern="^my_profile$"))
    app.add_handler(CallbackQueryHandler(back_home, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(lambda u,c: show_menu(u,c,"Help: Find Match -> Pay -> Send Receipt -> Admin approves"), pattern="^help$"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    print("LoveConnect Professional Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
