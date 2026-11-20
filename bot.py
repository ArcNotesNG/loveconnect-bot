import sqlite3, logging, datetime, os, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

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

NAME, AGE, GENDER, LOCATION, BIO, PHOTO, PREF_GENDER, PREF_AGE, PREF_COUNTRY, PREF_STATE, EDIT_PREF_GENDER, EDIT_PREF_AGE, EDIT_PREF_COUNTRY, EDIT_PREF_STATE = range(14)
logging.basicConfig(level=logging.INFO)

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
        pref_gender TEXT DEFAULT 'Anyone',
        pref_age_min INTEGER DEFAULT 18,
        pref_age_max INTEGER DEFAULT 70,
        pref_country TEXT DEFAULT 'Nigeria',
        pref_state TEXT DEFAULT 'Any',
        is_premium INTEGER DEFAULT 0, premium_until TEXT,
        created_at TEXT, is_banned INTEGER DEFAULT 0
    )""")
    cols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
    for col, default in [("pref_gender","'Anyone'"),("pref_age_min","18"),("pref_age_max","70"),("pref_country","'Nigeria'"),("pref_state","'Any'")]:
        if col not in cols:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} DEFAULT {default}")
    c.execute("""CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, plan TEXT, amount INTEGER,
        receipt_file_id TEXT, status TEXT DEFAULT 'pending',
        created_at TEXT, approved_by INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS seen (viewer_id INTEGER, viewed_id INTEGER, UNIQUE(viewer_id, viewed_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS likes (liker_id INTEGER, liked_id INTEGER, created_at TEXT, UNIQUE(liker_id, liked_id))""")
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
        [InlineKeyboardButton("🇳🇬 Nigeria", callback_data="country_Nigeria"), InlineKeyboardButton("🇬🇭 Ghana", callback_data="country_Ghana")],
        [InlineKeyboardButton("🇰🇪 Kenya", callback_data="country_Kenya"), InlineKeyboardButton("🌍 Other", callback_data="country_Other")],
    ]
    await q.edit_message_text("What country are you in?", reply_markup=InlineKeyboardMarkup(kb))
    return LOCATION

async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["country"] = q.data.split("_",1)[1]
    await q.edit_message_text("What State / City are you in? (e.g Lagos - Lekki, Abuja, Port Harcourt)\n\nJust type it:")
    return BIO

async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "location" not in context.user_data:
        context.user_data["location"] = update.message.text.strip()[:100]
        await update.message.reply_text("Write a short bio about yourself (e.g I love music, gym, and good food).")
        return BIO
    context.user_data["bio"] = update.message.text.strip()[:200]
    await update.message.reply_text("Send one clear photo of yourself.")
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Please send a photo.")
        return PHOTO
    context.user_data["photo_id"] = update.message.photo[-1].file_id
    kb = [
        [InlineKeyboardButton("👨 Men", callback_data="pref_gender_Male"), InlineKeyboardButton("👩 Women", callback_data="pref_gender_Female")],
        [InlineKeyboardButton("👨‍👩‍👧 Anyone", callback_data="pref_gender_Anyone")],
    ]
    await update.message.reply_text("✅ Photo saved!\n\nNow, let's set what you are looking for.\n\n**Who do you want to meet?**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return PREF_GENDER

async def get_pref_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["pref_gender"] = q.data.split("_",2)[2]
    kb = [
        [InlineKeyboardButton("18 - 25", callback_data="pref_age_18_25"), InlineKeyboardButton("26 - 35", callback_data="pref_age_26_35")],
        [InlineKeyboardButton("36 - 45", callback_data="pref_age_36_45"), InlineKeyboardButton("46 - 70", callback_data="pref_age_46_70")],
        [InlineKeyboardButton("Any Age (18-70)", callback_data="pref_age_18_70")],
    ]
    await q.edit_message_text("What age range do you want?", reply_markup=InlineKeyboardMarkup(kb))
    return PREF_AGE

async def get_pref_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts = q.data.split("_")
    context.user_data["pref_age_min"] = int(parts[2]); context.user_data["pref_age_max"] = int(parts[3])
    kb = [
        [InlineKeyboardButton("🇳🇬 Nigeria", callback_data="pref_country_Nigeria"), InlineKeyboardButton("🇬🇭 Ghana", callback_data="pref_country_Ghana")],
        [InlineKeyboardButton("🇰🇪 Kenya", callback_data="pref_country_Kenya"), InlineKeyboardButton("🌍 Any Country", callback_data="pref_country_Any")],
    ]
    await q.edit_message_text("What country should your match be from?", reply_markup=InlineKeyboardMarkup(kb))
    return PREF_COUNTRY

async def get_pref_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["pref_country"] = q.data.split("_",2)[2]
    await q.edit_message_text("What State / City should your match be in?\n\nType it (e.g Lagos, Abuja) or type *Any* for anywhere:", parse_mode="Markdown")
    return PREF_STATE

async def get_pref_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pref_state"] = update.message.text.strip()[:100]
    u = update.effective_user
    c = db()
    c.execute("""INSERT OR REPLACE INTO users (user_id, username, name, age, gender, location, bio, photo_id,
        pref_gender, pref_age_min, pref_age_max, pref_country, pref_state, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (u.id, u.username, context.user_data["name"], context.user_data["age"], context.user_data["gender"],
         f"{context.user_data.get('country','Nigeria')} - {context.user_data['location']}",
         context.user_data["bio"], context.user_data["photo_id"],
         context.user_data["pref_gender"], context.user_data["pref_age_min"], context.user_data["pref_age_max"],
         context.user_data["pref_country"], context.user_data["pref_state"],
         datetime.datetime.now().isoformat()))
    c.commit(); c.close()
    await update.message.reply_text(f"✅ Profile created!\n\nYour preferences:\n• Looking for: {context.user_data['pref_gender']}\n• Age: {context.user_data['pref_age_min']}-{context.user_data['pref_age_max']}\n• Country: {context.user_data['pref_country']}\n• State/City: {context.user_data['pref_state']}\n\nLet's find your match!")
    await show_menu(update, context, "Profile ready 💖")
    return ConversationHandler.END

async def edit_prefs_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [
        [InlineKeyboardButton("👨 Men", callback_data="edit_gender_Male"), InlineKeyboardButton("👩 Women", callback_data="edit_gender_Female")],
        [InlineKeyboardButton("👨‍👩‍👧 Anyone", callback_data="edit_gender_Anyone")],
    ]
    await q.edit_message_text("⚙️ Edit Preferences\n\nWho do you want to meet?", reply_markup=InlineKeyboardMarkup(kb))
    return EDIT_PREF_GENDER

async def edit_pref_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["edit_pref_gender"] = q.data.split("_",2)[2]
    kb = [
        [InlineKeyboardButton("18 - 25", callback_data="edit_age_18_25"), InlineKeyboardButton("26 - 35", callback_data="edit_age_26_35")],
        [InlineKeyboardButton("36 - 45", callback_data="edit_age_36_45"), InlineKeyboardButton("46 - 70", callback_data="edit_age_46_70")],
        [InlineKeyboardButton("Any Age (18-70)", callback_data="edit_age_18_70")],
    ]
    await q.edit_message_text("What age range do you want?", reply_markup=InlineKeyboardMarkup(kb))
    return EDIT_PREF_AGE

async def edit_pref_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts = q.data.split("_")
    context.user_data["edit_pref_min"] = int(parts[2]); context.user_data["edit_pref_max"] = int(parts[3])
    kb = [
        [InlineKeyboardButton("🇳🇬 Nigeria", callback_data="edit_country_Nigeria"), InlineKeyboardButton("🇬🇭 Ghana", callback_data="edit_country_Ghana")],
        [InlineKeyboardButton("🇰🇪 Kenya", callback_data="edit_country_Kenya"), InlineKeyboardButton("🌍 Any Country", callback_data="edit_country_Any")],
    ]
    await q.edit_message_text("What country should your match be from?", reply_markup=InlineKeyboardMarkup(kb))
    return EDIT_PREF_COUNTRY

async def edit_pref_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["edit_pref_country"] = q.data.split("_",2)[2]
    await q.edit_message_text("What State / City should your match be in? Type it or type Any:")
    return EDIT_PREF_STATE

async def edit_pref_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    c = db()
    c.execute("UPDATE users SET pref_gender=?, pref_age_min=?, pref_age_max=?, pref_country=?, pref_state=? WHERE user_id=?",
        (context.user_data["edit_pref_gender"], context.user_data["edit_pref_min"], context.user_data["edit_pref_max"], context.user_data["edit_pref_country"], update.message.text.strip()[:100], uid))
    c.commit(); c.close()
    c = db(); c.execute("DELETE FROM seen WHERE viewer_id=?", (uid,)); c.commit(); c.close()
    await update.message.reply_text("✅ Preferences updated! Your matches will now use your new preferences.")
    await show_menu(update, context, "Preferences saved 💖")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Send /start to try again.")
    return ConversationHandler.END

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="Main Menu"):
    kb = [
        [InlineKeyboardButton("💖 Find Match", callback_data="find_match")],
        [InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],
        [InlineKeyboardButton("⚙️ My Preferences", callback_data="my_prefs")],
        [InlineKeyboardButton("🔓 Unlock / Premium", callback_data="unlock_menu")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ]
    markup = InlineKeyboardMarkup(kb)
    if update.callback_query:
        try: await update.callback_query.edit_message_text(text, reply_markup=markup)
        except: await update.callback_query.message.reply_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)

async def do_find_match(uid, chat_id, context, edit_message=None):
    me = get_user(uid)
    if not me:
        return None
    pref_gender = me["pref_gender"] or "Anyone"
    pref_min = me["pref_age_min"] or 18
    pref_max = me["pref_age_max"] or 70
    c = db()
    query = """SELECT * FROM users WHERE user_id != ? AND is_banned=0 AND age BETWEEN ? AND ? AND user_id NOT IN (SELECT viewed_id FROM seen WHERE viewer_id=?)"""
    params = [uid, pref_min, pref_max, uid]
    if pref_gender != "Anyone":
        query += " AND gender=?"; params.append(pref_gender)
    query += " ORDER BY RANDOM() LIMIT 1"
    row = c.execute(query, tuple(params)).fetchone()
    if not row:
        c.execute("DELETE FROM seen WHERE viewer_id=?", (uid,)); c.commit()
        row = c.execute(query, tuple(params)).fetchone()
    if not row:
        kb = [
            [InlineKeyboardButton("🔄 Try Again - Find Match", callback_data="find_match")],
            [InlineKeyboardButton("⚙️ Change My Preferences", callback_data="my_prefs")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_home")],
        ]
        text = "No new matches for your preferences yet. 😔\n\nThis does NOT mean nobody is online. It means no one matches your age/gender filter yet.\n\nTap Try Again, or change your preferences to Any / wider age to see more people."
        if edit_message:
            await edit_message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await context.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(kb))
        c.close(); return False
    c.execute("INSERT OR IGNORE INTO seen VALUES (?,?)", (uid, row["user_id"])); c.commit(); c.close()
    context.user_data["current_match_id"] = row["user_id"]
    premium = is_premium(uid)
    username_display = f"@{row['username']}" if (premium and row["username"]) else "🔒 ******* (Locked - Unlock to see)"
    kb = [
        [InlineKeyboardButton("🔓 Unlock Match", callback_data="unlock_menu")],
        [InlineKeyboardButton("❤️ Like", callback_data="like_match"), InlineKeyboardButton("⏭️ Next", callback_data="find_match")],
    ]
    await context.bot.send_photo(chat_id, row["photo_id"],
        caption=f"💖 *{row['name']}, {row['age']}*\n📍 {row['location']}\n📝 {row['bio']}\n\nUsername: {username_display}",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return True

async def find_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await do_find_match(q.from_user.id, q.message.chat_id, context)

async def like_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    match_id = context.user_data.get("current_match_id")
    if not match_id:
        await q.edit_message_text("Find a match first."); return
    c = db(); c.execute("INSERT OR IGNORE INTO likes VALUES (?,?,?)", (q.from_user.id, match_id, datetime.datetime.now().isoformat())); c.commit(); c.close()
    try: await context.bot.send_message(match_id, "💖 Someone liked your profile! Open LoveConnect to see who.")
    except: pass
    await q.edit_message_text("❤️ Like sent! They will see it when they open the bot.")

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
    await q.edit_message_text("🔓 *Unlock Match*\n\nChoose plan:\n\n*Weekly ₦1,500* - 7 days\n*Monthly ₦3,500* - 30 days - Most Popular\n*3 Months ₦8,000* - 90 days - Best Value\n\n1. Tap Pay (Paystack)\n2. Screenshot receipt\n3. Tap I Have Paid & send receipt", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def i_have_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [[InlineKeyboardButton(v["label"], callback_data=f"paid_{k}")] for k,v in PLANS.items()]
    await q.edit_message_text("Which plan did you pay for?", reply_markup=InlineKeyboardMarkup(kb))

async def paid_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    plan = q.data.replace("paid_", "")
    context.user_data["pending_plan"] = plan; context.user_data["waiting_receipt"] = True
    await q.edit_message_text(f"You selected *{PLANS[plan]['label']}*.\n\nNow send your Paystack receipt screenshot as PHOTO.\n\n⚠️ Fake receipts = permanent ban.", parse_mode="Markdown")

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_receipt"): return
    if not update.message.photo:
        await update.message.reply_text("Send receipt as PHOTO, not file."); return
    uid = update.effective_user.id
    plan = context.user_data.get("pending_plan", "weekly")
    context.user_data["waiting_receipt"] = False
    file_id = update.message.photo[-1].file_id
    c = db(); c.execute("INSERT INTO payments (user_id, plan, amount, receipt_file_id, created_at) VALUES (?,?,?,?,?)", (uid, plan, PLANS[plan]["price"], file_id, datetime.datetime.now().isoformat())); c.commit(); c.close()
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{plan}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]]
    await context.bot.send_message(ADMIN_ID, f"💰 *NEW PAYMENT*\nUser: @{update.effective_user.username} ({uid})\nPlan: {PLANS[plan]['label']} - ₦{PLANS[plan]['price']}\n\nCheck receipt & Paystack dashboard before approving!", parse_mode="Markdown")
    await context.bot.send_photo(ADMIN_ID, file_id, caption=f"Receipt from {uid} - {plan}", reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("✅ Receipt received. Admin will verify on Paystack and approve.")

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id != ADMIN_ID:
        await q.edit_message_text("Not admin."); return
    parts = q.data.split("_"); action = parts[0]; uid = int(parts[1])
    if action == "approve":
        plan = parts[2]; days = PLANS[plan]["days"]; until = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
        c = db(); c.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?", (until, uid)); c.execute("UPDATE payments SET status='approved', approved_by=? WHERE user_id=? AND status='pending'", (ADMIN_ID, uid)); c.commit(); c.close()
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

async def my_prefs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    u = get_user(q.from_user.id)
    if not u: await q.edit_message_text("Send /start to create profile."); return
    kb = [[InlineKeyboardButton("✏️ Edit Preferences", callback_data="edit_prefs")],[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]
    await q.edit_message_text(f"⚙️ *Your Preferences*\n\n• Looking for: {u['pref_gender']}\n• Age: {u['pref_age_min']}-{u['pref_age_max']}\n• Country: {u['pref_country']}\n• State/City: {u['pref_state']}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def back_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await show_menu(update, context, "Welcome back 💖")

async def cmd_findmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    me = get_user(uid)
    if not me:
        await update.message.reply_text("Please send /start to create profile first.")
        return
    await do_find_match(uid, update.effective_chat.id, context)

async def cmd_myprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u: await update.message.reply_text("Send /start to create profile."); return
    await update.message.reply_text(f"👤 {u['name']}, {u['age']}\n📍 {u['location']}\n📝 {u['bio']}")
async def cmd_myprefs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u: await update.message.reply_text("Send /start to create profile."); return
    kb = [[InlineKeyboardButton("✏️ Edit Preferences", callback_data="edit_prefs")],[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]
    await update.message.reply_text(f"⚙️ *Your Preferences*\n\n• Looking for: {u['pref_gender']}\n• Age: {u['pref_age_min']}-{u['pref_age_max']}\n• Country: {u['pref_country']}\n• State/City: {u['pref_state']}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send /start then tap Unlock / Premium to see plans.")
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Help: Find Match -> Pay -> Send Receipt -> Admin approves")

async def set_menu_commands(app):
    commands = [
        BotCommand("start", "Start / Create Profile"),
        BotCommand("findmatch", "Find a Match"),
        BotCommand("myprofile", "View My Profile"),
        BotCommand("myprefs", "My Preferences"),
        BotCommand("premium", "Unlock Premium"),
        BotCommand("help", "Help"),
    ]
    await app.bot.set_my_commands(commands)

def main():
    asyncio.set_event_loop(asyncio.new_event_loop())
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = set_menu_commands
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
                GENDER: [CallbackQueryHandler(get_gender, pattern="^gender_")],
                LOCATION: [CallbackQueryHandler(get_location, pattern="^country_")],
                BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
                PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
                PREF_GENDER: [CallbackQueryHandler(get_pref_gender, pattern="^pref_gender_")],
                PREF_AGE: [CallbackQueryHandler(get_pref_age, pattern="^pref_age_")],
                PREF_COUNTRY: [CallbackQueryHandler(get_pref_country, pattern="^pref_country_")],
                PREF_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pref_state)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_prefs_start, pattern="^edit_prefs$")],
        states={EDIT_PREF_GENDER: [CallbackQueryHandler(edit_pref_gender, pattern="^edit_gender_")],
                EDIT_PREF_AGE: [CallbackQueryHandler(edit_pref_age, pattern="^edit_age_")],
                EDIT_PREF_COUNTRY: [CallbackQueryHandler(edit_pref_country, pattern="^edit_country_")],
                EDIT_PREF_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pref_state)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(conv)
    app.add_handler(edit_conv)
    app.add_handler(CommandHandler("findmatch", cmd_findmatch))
    app.add_handler(CommandHandler("myprofile", cmd_myprofile))
    app.add_handler(CommandHandler("myprefs", cmd_myprefs))
    app.add_handler(CommandHandler("premium", cmd_premium))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(find_match, pattern="^find_match$"))
    app.add_handler(CallbackQueryHandler(like_match, pattern="^like_match$"))
    app.add_handler(CallbackQueryHandler(unlock_menu, pattern="^unlock_menu$"))
    app.add_handler(CallbackQueryHandler(i_have_paid, pattern="^i_have_paid$"))
    app.add_handler(CallbackQueryHandler(paid_selected, pattern="^paid_"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(my_profile, pattern="^my_profile$"))
    app.add_handler(CallbackQueryHandler(my_prefs, pattern="^my_prefs$"))
    app.add_handler(CallbackQueryHandler(back_home, pattern="^back_home$"))
    app.add_handler(CallbackQueryHandler(lambda u,c: show_menu(u,c,"Help: Find Match -> Pay -> Send Receipt -> Admin approves"), pattern="^help$"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    print("LoveConnect Professional Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
