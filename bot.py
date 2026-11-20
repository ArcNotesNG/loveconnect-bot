import sqlite3, logging, datetime, os, asyncio, threading, traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"LoveConnect Bot is Running")
    def log_message(self, *args): pass

def keep_alive():
    try: HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), Handler).serve_forever()
    except Exception as e: print(f"Keep alive failed: {e}")
threading.Thread(target=keep_alive, daemon=True).start()

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
DB_FILE = "loveconnect.db"
WEEKLY_LINK = "https://paystack.shop/pay/loveconnect-weekly"
MONTHLY_LINK = "https://paystack.shop/pay/loveconnect-monthly"
THREE_MONTHS_LINK = "https://paystack.shop/pay/loveconnect-3months"
PLANS = {"weekly": {"price": 1500, "days": 7, "label": "Weekly - ₦1,500", "link": WEEKLY_LINK},
"monthly": {"price": 3500, "days": 30, "label": "Monthly - ₦3,500", "link": MONTHLY_LINK},
"3months": {"price": 8000, "days": 90, "label": "3 Months - ₦8,000", "link": THREE_MONTHS_LINK}}
NAME, AGE, GENDER, LOCATION, BIO, PHOTO, PREF_GENDER, PREF_AGE, PREF_COUNTRY, PREF_STATE, EDIT_PREF_GENDER, EDIT_PREF_AGE, EDIT_PREF_COUNTRY, EDIT_PREF_STATE = range(14)
logging.basicConfig(level=logging.INFO)

def db():
    c = sqlite3.connect(DB_FILE); c.row_factory = sqlite3.Row; return c

def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, name TEXT, age INTEGER, gender TEXT, location TEXT, bio TEXT, photo_id TEXT, pref_gender TEXT DEFAULT 'Anyone', pref_age_min INTEGER DEFAULT 18, pref_age_max INTEGER DEFAULT 70, pref_country TEXT DEFAULT 'Nigeria', pref_state TEXT DEFAULT 'Any', is_premium INTEGER DEFAULT 0, premium_until TEXT, created_at TEXT, is_banned INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan TEXT, amount INTEGER, receipt_file_id TEXT, status TEXT DEFAULT 'pending', created_at TEXT, approved_by INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS seen (viewer_id INTEGER, viewed_id INTEGER, UNIQUE(viewer_id, viewed_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS likes (liker_id INTEGER, liked_id INTEGER, created_at TEXT, UNIQUE(liker_id, liked_id))""")
    c.commit(); c.close()

def get_user(uid):
    c = db(); r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone(); c.close(); return r

def is_premium(uid):
    u = get_user(uid)
    if not u or not u["is_premium"]: return False
    if u["premium_until"]:
        try:
            if datetime.datetime.now() > datetime.datetime.fromisoformat(u["premium_until"]):
                c = db(); c.execute("UPDATE users SET is_premium=0 WHERE user_id=?", (uid,)); c.commit(); c.close(); return False
            return True
        except: return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if u:
        await show_menu(update, context, f"Welcome back, {u['name']} 💖"); return ConversationHandler.END
    await update.message.reply_text("Welcome to *LoveConnect* 💖\nNigeria's Real Dating Bot.\n\nLet's create your profile.\n\nWhat is your name?"); return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip(); await update.message.reply_text("How old are you? (e.g 24)"); return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
        if age < 18 or age > 70: await update.message.reply_text("You must be 18-70. Try again:"); return AGE
    except: await update.message.reply_text("Send number only, e.g 24"); return AGE
    context.user_data["age"] = age
    kb = [[InlineKeyboardButton("👨 Male", callback_data="gender_Male"), InlineKeyboardButton("👩 Female", callback_data="gender_Female")]]
    await update.message.reply_text("Are you Male or Female?", reply_markup=InlineKeyboardMarkup(kb)); return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); context.user_data["gender"] = q.data.split("_")[1]
    kb = [[InlineKeyboardButton("🇳🇬 Nigeria", callback_data="country_Nigeria"), InlineKeyboardButton("🇬🇭 Ghana", callback_data="country_Ghana")],[InlineKeyboardButton("🇰🇪 Kenya", callback_data="country_Kenya"), InlineKeyboardButton("🌍 Other", callback_data="country_Other")]]
    await q.edit_message_text("What country are you in?", reply_markup=InlineKeyboardMarkup(kb)); return LOCATION

async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); context.user_data["country"] = q.data.split("_",1)[1]
    await q.edit_message_text("What State / City are you in? (e.g Lagos - Lekki, Abuja)\n\nJust type it:"); return BIO

async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "location" not in context.user_data:
        context.user_data["location"] = update.message.text.strip()[:100]; await update.message.reply_text("Write a short bio about yourself (e.g I love music, gym, and good food)."); return BIO
    context.user_data["bio"] = update.message.text.strip()[:200]; await update.message.reply_text("Send one clear photo of yourself."); return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo: await update.message.reply_text("Please send a photo."); return PHOTO
    context.user_data["photo_id"] = update.message.photo[-1].file_id
    kb = [[InlineKeyboardButton("👨 Men", callback_data="pref_gender_Male"), InlineKeyboardButton("👩 Women", callback_data="pref_gender_Female")],[InlineKeyboardButton("👨‍👩‍👧 Anyone", callback_data="pref_gender_Anyone")]]
    await update.message.reply_text("✅ Photo saved!\n\nNow, let's set what you are looking for.\n\n**Who do you want to meet?**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"); return PREF_GENDER

async def get_pref_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); context.user_data["pref_gender"] = q.data.split("_",2)[2]
    kb = [[InlineKeyboardButton("18 - 25", callback_data="pref_age_18_25"), InlineKeyboardButton("26 - 35", callback_data="pref_age_26_35")],[InlineKeyboardButton("36 - 45", callback_data="pref_age_36_45"), InlineKeyboardButton("46 - 70", callback_data="pref_age_46_70")],[InlineKeyboardButton("Any Age (18-70)", callback_data="pref_age_18_70")]]
    await q.edit_message_text("What age range do you want?", reply_markup=InlineKeyboardMarkup(kb)); return PREF_AGE

async def get_pref_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); p = q.data.split("_"); context.user_data["pref_age_min"] = int(p[2]); context.user_data["pref_age_max"] = int(p[3])
    kb = [[InlineKeyboardButton("🇳🇬 Nigeria", callback_data="pref_country_Nigeria"), InlineKeyboardButton("🇬🇭 Ghana", callback_data="pref_country_Ghana")],[InlineKeyboardButton("🇰🇪 Kenya", callback_data="pref_country_Kenya"), InlineKeyboardButton("🌍 Any Country", callback_data="pref_country_Any")]]
    await q.edit_message_text("What country should your match be from?", reply_markup=InlineKeyboardMarkup(kb)); return PREF_COUNTRY

async def get_pref_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); context.user_data["pref_country"] = q.data.split("_",2)[2]
    await q.edit_message_text("What State / City should your match be in?\n\nType it (e.g Lagos, Abuja) or type *Any*:", parse_mode="Markdown"); return PREF_STATE

async def get_pref_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pref_state"] = update.message.text.strip()[:100]; u = update.effective_user; c = db()
    c.execute("""INSERT INTO users (user_id, username, name, age, gender, location, bio, photo_id, pref_gender, pref_age_min, pref_age_max, pref_country, pref_state, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, name=excluded.name, age=excluded.age, gender=excluded.gender, location=excluded.location, bio=excluded.bio, photo_id=excluded.photo_id, pref_gender=excluded.pref_gender, pref_age_min=excluded.pref_age_min, pref_age_max=excluded.pref_age_max, pref_country=excluded.pref_country, pref_state=excluded.pref_state""", (u.id, u.username, context.user_data["name"], context.user_data["age"], context.user_data["gender"], f"{context.user_data.get('country','Nigeria')} - {context.user_data['location']}", context.user_data["bio"], context.user_data["photo_id"], context.user_data["pref_gender"], context.user_data["pref_age_min"], context.user_data["pref_age_max"], context.user_data["pref_country"], context.user_data["pref_state"], datetime.datetime.now().isoformat()))
    c.commit(); c.close()
    await update.message.reply_text(f"✅ Profile created!\n\nLooking for: {context.user_data['pref_gender']} | Age: {context.user_data['pref_age_min']}-{context.user_data['pref_age_max']} | {context.user_data['pref_country']} - {context.user_data['pref_state']}")
    await show_menu(update, context, "Profile ready 💖"); return ConversationHandler.END

async def edit_prefs_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [[InlineKeyboardButton("👨 Men", callback_data="edit_gender_Male"), InlineKeyboardButton("👩 Women", callback_data="edit_gender_Female")],[InlineKeyboardButton("👨‍👩‍👧 Anyone", callback_data="edit_gender_Anyone")]]
    await q.edit_message_text("⚙️ Edit Preferences\n\nWho do you want to meet?", reply_markup=InlineKeyboardMarkup(kb)); return EDIT_PREF_GENDER

async def edit_pref_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); context.user_data["edit_pref_gender"] = q.data.split("_",2)[2]
    kb = [[InlineKeyboardButton("18 - 25", callback_data="edit_age_18_25"), InlineKeyboardButton("26 - 35", callback_data="edit_age_26_35")],[InlineKeyboardButton("36 - 45", callback_data="edit_age_36_45"), InlineKeyboardButton("46 - 70", callback_data="edit_age_46_70")],[InlineKeyboardButton("Any Age (18-70)", callback_data="edit_age_18_70")]]
    await q.edit_message_text("What age range do you want?", reply_markup=InlineKeyboardMarkup(kb)); return EDIT_PREF_AGE

async def edit_pref_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); p = q.data.split("_"); context.user_data["edit_pref_min"] = int(p[2]); context.user_data["edit_pref_max"] = int(p[3])
    kb = [[InlineKeyboardButton("🇳🇬 Nigeria", callback_data="edit_country_Nigeria"), InlineKeyboardButton("🇬🇭 Ghana", callback_data="edit_country_Ghana")],[InlineKeyboardButton("🇰🇪 Kenya", callback_data="edit_country_Kenya"), InlineKeyboardButton("🌍 Any Country", callback_data="edit_country_Any")]]
    await q.edit_message_text("What country should your match be from?", reply_markup=InlineKeyboardMarkup(kb)); return EDIT_PREF_COUNTRY

async def edit_pref_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); context.user_data["edit_pref_country"] = q.data.split("_",2)[2]
    await q.edit_message_text("What State / City should your match be in? Type it or type Any:"); return EDIT_PREF_STATE

async def edit_pref_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; c = db()
    c.execute("UPDATE users SET pref_gender=?, pref_age_min=?, pref_age_max=?, pref_country=?, pref_state=? WHERE user_id=?", (context.user_data["edit_pref_gender"], context.user_data["edit_pref_min"], context.user_data["edit_pref_max"], context.user_data["edit_pref_country"], update.message.text.strip()[:100], uid)); c.commit(); c.close()
    c = db(); c.execute("DELETE FROM seen WHERE viewer_id=?", (uid,)); c.commit(); c.close()
    await update.message.reply_text("✅ Preferences updated!"); await show_menu(update, context, "Preferences saved 💖"); return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Send /start to try again."); return ConversationHandler.END

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="Main Menu"):
    kb = [[InlineKeyboardButton("💖 Find Match", callback_data="find_match")],[InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],[InlineKeyboardButton("⚙️ My Preferences", callback_data="my_prefs")],[InlineKeyboardButton("🔓 Unlock / Premium", callback_data="unlock_menu")],[InlineKeyboardButton("ℹ️ Help", callback_data="help")]]
    m = InlineKeyboardMarkup(kb)
    if update.callback_query:
        try: await update.callback_query.edit_message_text(text, reply_markup=m)
        except: await update.callback_query.message.reply_text(text, reply_markup=m)
    else: await update.message.reply_text(text, reply_markup=m)

async def do_find_match(uid, chat_id, context):
    try:
        await context.bot.send_message(chat_id, "🔍 Searching for your match...")
        me = get_user(uid)
        if not me: await context.bot.send_message(chat_id, "Send /start to create profile first."); return False
        c = db()
        q = "SELECT * FROM users WHERE user_id != ? AND user_id NOT IN (SELECT viewed_id FROM seen WHERE viewer_id=?) AND age BETWEEN ? AND ?"
        params = [uid, uid, me["pref_age_min"], me["pref_age_max"]]
        if me["pref_gender"] != "Anyone": q += " AND gender=?"; params.append(me["pref_gender"])
        if me["pref_country"] != "Any": q += " AND location LIKE ?"; params.append(f"{me['pref_country']}%")
        if me["pref_state"] and me["pref_state"].lower() != "any": q += " AND location LIKE ?"; params.append(f"%{me['pref_state']}%")
        q += " ORDER BY RANDOM() LIMIT 1"
        row = c.execute(q, params).fetchone()
        if not row:
            row = c.execute("SELECT * FROM users WHERE user_id != ? ORDER BY RANDOM() LIMIT 1", (uid,)).fetchone()
        c.close()
        if not row: await context.bot.send_message(chat_id, "No other user found. Create 2nd profile on other account and try again."); return False
        c = db(); c.execute("INSERT OR IGNORE INTO seen VALUES (?,?)", (uid, row["user_id"])); c.commit(); c.close()
        context.user_data["current_match_id"] = row["user_id"]
        premium = is_premium(uid)
        if premium:
            contact = f"Username: @{row['username'] if row['username'] else 'No username'} ✅\n\nYou can message them now!"
            kb = [[InlineKeyboardButton("❤️ Like", callback_data="like_match"), InlineKeyboardButton("⏭️ Next", callback_data="find_match")]]
        else:
            contact = "🔒 Username Hidden\n\nPay ₦1,500 to unlock this person's Telegram username."
            kb = [[InlineKeyboardButton("❤️ Like", callback_data="like_match"), InlineKeyboardButton("⏭️ Next", callback_data="find_match")],[InlineKeyboardButton("🔓 Unlock Username - ₦1,500", callback_data="unlock_menu")]]
        caption = f"💖 {row['name']}, {row['age']}\n📍 {row['location']}\n📝 {row['bio']}\n\n{contact}"
        try: await context.bot.send_photo(chat_id, row["photo_id"], caption=caption, reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e: await context.bot.send_message(chat_id, caption + f"\n\n(Photo failed: {e})", reply_markup=InlineKeyboardMarkup(kb))
        return True
    except Exception as e:
        print(f"FIND MATCH ERROR: {e}"); traceback.print_exc(); await context.bot.send_message(chat_id, f"⚠️ REAL ERROR IS:\n\n{e}"); return False

async def find_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try: await q.answer()
    except: pass
    await do_find_match(q.from_user.id, q.message.chat_id, context)

async def like_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); match_id = context.user_data.get("current_match_id")
    if not match_id: await q.edit_message_text("Find a match first."); return
    c = db(); c.execute("INSERT OR IGNORE INTO likes VALUES (?,?,?)", (q.from_user.id, match_id, datetime.datetime.now().isoformat())); c.commit(); c.close()
    try: await context.bot.send_message(match_id, "💖 Someone liked your profile! Open LoveConnect to see who.")
    except: pass
    await q.edit_message_text("❤️ Like sent!")

async def unlock_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id
    if is_premium(uid):
        u = get_user(uid); await q.edit_message_text(f"✅ You are Premium until {u['premium_until'][:10]}."); return
    kb = [[InlineKeyboardButton("💳 Weekly - ₦1,500 (7 days)", url=PLANS["weekly"]["link"])],[InlineKeyboardButton("💳 Monthly - ₦3,500 (30 days) ⭐", url=PLANS["monthly"]["link"])],[InlineKeyboardButton("💳 3 Months - ₦8,000 (90 days) 🔥", url=PLANS["3months"]["link"])],[InlineKeyboardButton("✅ I Have Paid", callback_data="i_have_paid")],[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]
    await q.edit_message_text("🔓 *Unlock Match*\n\nChoose plan:\n\n*Weekly ₦1,500* - 7 days\n*Monthly ₦3,500* - 30 days - Most Popular\n*3 Months ₦8,000* - 90 days - Best Value\n\n1. Tap Pay (Paystack)\n2. Screenshot receipt\n3. Tap I Have Paid & send receipt", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def i_have_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [[InlineKeyboardButton(v["label"], callback_data=f"paid_{k}")] for k,v in PLANS.items()]
    await q.edit_message_text("Which plan did you pay for?", reply_markup=InlineKeyboardMarkup(kb))

async def paid_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); plan = q.data.replace("paid_", "")
    context.user_data["pending_plan"] = plan; context.user_data["waiting_receipt"] = True
    await q.edit_message_text(f"You selected *{PLANS[plan]['label']}*.\n\nNow send your Paystack receipt screenshot as PHOTO.\n\n⚠️ Fake receipts = permanent ban.", parse_mode="Markdown")

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_receipt"): return
    if not update.message.photo: await update.message.reply_text("Send receipt as PHOTO, not file."); return
    uid = update.effective_user.id; plan = context.user_data.get("pending_plan", "weekly"); context.user_data["waiting_receipt"] = False; file_id = update.message.photo[-1].file_id
    c = db(); c.execute("INSERT INTO payments (user_id, plan, amount, receipt_file_id, created_at) VALUES (?,?,?,?,?)", (uid, plan, PLANS[plan]["price"], file_id, datetime.datetime.now().isoformat())); c.commit(); c.close()
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{plan}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]]
    await context.bot.send_message(ADMIN_ID, f"💰 *NEW PAYMENT*\nUser: @{update.effective_user.username} ({uid})\nPlan: {PLANS[plan]['label']} - ₦{PLANS[plan]['price']}\n\nCheck receipt & Paystack dashboard before approving!", parse_mode="Markdown")
    await context.bot.send_photo(ADMIN_ID, file_id, caption=f"Receipt from {uid} - {plan}", reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("✅ Receipt received. Admin will verify on Paystack and approve.")

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id != ADMIN_ID: await q.edit_message_text("Not admin."); return
    parts = q.data.split("_"); action = parts[0]; uid = int(parts[1])
    if action == "approve":
        plan = parts[2]; days = PLANS[plan]["days"]; until = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
        c = db(); c.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?", (until, uid)); c.execute("UPDATE payments SET status='approved', approved_by=? WHERE user_id=? AND status='pending'", (ADMIN_ID, uid)); c.commit(); c.close()
        await context.bot.send_message(uid, f"🎉 *Payment Approved!*\n\nYour {PLANS[plan]['label']} is ACTIVE until {until[:10]}.\n\nNow go to Find Match - all usernames are unlocked! 💖", parse_mode="Markdown")
        # After approve, show Unapprove button so admin can undo for testing
        kb = [[InlineKeyboardButton("↩️ Unapprove / Revoke Premium", callback_data=f"revoke_{uid}")]]
        await q.edit_message_text(f"✅ Approved {uid} for {plan}\n\nTap below to undo if this was a test:", reply_markup=InlineKeyboardMarkup(kb))
    elif action == "revoke":
        c = db(); c.execute("UPDATE users SET is_premium=0, premium_until=NULL WHERE user_id=?", (uid,)); c.execute("UPDATE payments SET status='revoked' WHERE user_id=? AND status='approved'", (uid,)); c.execute("DELETE FROM seen WHERE viewer_id=?", (uid,)); c.commit(); c.close()
        try: await context.bot.send_message(uid, "🔒 Your Premium has been removed by Admin. You are now Free - usernames are locked again.")
        except: pass
        await q.edit_message_text(f"↩️ Revoked Premium for {uid}. They are Free again.")
    else:
        c = db(); c.execute("UPDATE payments SET status='rejected' WHERE user_id=? AND status='pending'", (uid,)); c.commit(); c.close()
        await context.bot.send_message(uid, "❌ Payment not confirmed. Please send correct receipt or contact support.")
        await q.edit_message_text(f"❌ Rejected {uid}")

async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); u = get_user(q.from_user.id)
    if not u: await q.edit_message_text("Send /start to create profile."); return
    status = f"Premium until {u['premium_until'][:10]} ✅" if is_premium(q.from_user.id) else "Free (Locked) 🔒"
    await q.edit_message_text(f"👤 *{u['name']}, {u['age']}*\n📍 {u['location']}\n📝 {u['bio']}\nStatus: {status}", parse_mode="Markdown")

async def my_prefs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); u = get_user(q.from_user.id)
    if not u: await q.edit_message_text("Send /start to create profile."); return
    kb = [[InlineKeyboardButton("✏️ Edit Preferences", callback_data="edit_prefs")],[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]
    await q.edit_message_text(f"⚙️ *Your Preferences*\n\n• Looking for: {u['pref_gender']}\n• Age: {u['pref_age_min']}-{u['pref_age_max']}\n• Country: {u['pref_country']}\n• State/City: {u['pref_state']}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def back_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); await show_menu(update, context, "Welcome back 💖")

async def cmd_findmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not get_user(uid): await update.message.reply_text("Please send /start to create profile first."); return
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

# --- NEW: REVOKE / UNAPPROVE ---
async def cmd_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: await update.message.reply_text("Not admin."); return
    if not context.args: await update.message.reply_text("Use: /revoke <user_id>\nExample: /revoke 123456789\n\nTip: send /myid from the test account to get its ID."); return
    try: target = int(context.args[0])
    except: await update.message.reply_text("User ID must be numbers only."); return
    c = db(); c.execute("UPDATE users SET is_premium=0, premium_until=NULL WHERE user_id=?", (target,)); c.execute("UPDATE payments SET status='revoked' WHERE user_id=? AND status='approved'", (target,)); c.execute("DELETE FROM seen WHERE viewer_id=?", (target,)); c.commit(); c.close()
    try: await context.bot.send_message(target, "🔒 Your Premium has been removed by Admin. You are now Free - usernames are locked again.")
    except: pass
    await update.message.reply_text(f"✅ Revoked Premium for {target}. They are Free again, can test from scratch.")

async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram ID is:\n`{update.effective_user.id}`\n\nCopy it and send to Admin for revoke.", parse_mode="Markdown")

async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send /start then tap Unlock / Premium to see plans.")
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Help: Find Match -> Pay -> Send Receipt -> Admin approves")
async def set_menu_commands(app):
    await app.bot.set_my_commands([BotCommand("start", "Start / Create Profile"), BotCommand("findmatch", "Find a Match"), BotCommand("myprofile", "View My Profile"), BotCommand("myprefs", "My Preferences"), BotCommand("premium", "Unlock Premium"), BotCommand("help", "Help")])

def main():
    asyncio.set_event_loop(asyncio.new_event_loop()); init_db(); app = Application.builder().token(BOT_TOKEN).build(); app.post_init = set_menu_commands
    conv = ConversationHandler(entry_points=[CommandHandler("start", start)], states={NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)], AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)], GENDER: [CallbackQueryHandler(get_gender, pattern="^gender_")], LOCATION: [CallbackQueryHandler(get_location, pattern="^country_")], BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)], PHOTO: [MessageHandler(filters.PHOTO, get_photo)], PREF_GENDER: [CallbackQueryHandler(get_pref_gender, pattern="^pref_gender_")], PREF_AGE: [CallbackQueryHandler(get_pref_age, pattern="^pref_age_")], PREF_COUNTRY: [CallbackQueryHandler(get_pref_country, pattern="^pref_country_")], PREF_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pref_state)]}, fallbacks=[CommandHandler("cancel", cancel)], allow_reentry=True)
    edit_conv = ConversationHandler(entry_points=[CallbackQueryHandler(edit_prefs_start, pattern="^edit_prefs$")], states={EDIT_PREF_GENDER: [CallbackQueryHandler(edit_pref_gender, pattern="^edit_gender_")], EDIT_PREF_AGE: [CallbackQueryHandler(edit_pref_age, pattern="^edit_age_")], EDIT_PREF_COUNTRY: [CallbackQueryHandler(edit_pref_country, pattern="^edit_country_")], EDIT_PREF_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pref_state)]}, fallbacks=[CommandHandler("cancel", cancel)], allow_reentry=True)
    app.add_handler(conv); app.add_handler(edit_conv)
    app.add_handler(CommandHandler("findmatch", cmd_findmatch)); app.add_handler(CommandHandler("myprofile", cmd_myprofile)); app.add_handler(CommandHandler("myprefs", cmd_myprefs)); app.add_handler(CommandHandler("premium", cmd_premium)); app.add_handler(CommandHandler("help", cmd_help)); app.add_handler(CommandHandler("revoke", cmd_revoke)); app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CallbackQueryHandler(find_match, pattern="^find_match$")); app.add_handler(CallbackQueryHandler(like_match, pattern="^like_match$")); app.add_handler(CallbackQueryHandler(unlock_menu, pattern="^unlock_menu$")); app.add_handler(CallbackQueryHandler(i_have_paid, pattern="^i_have_paid$")); app.add_handler(CallbackQueryHandler(paid_selected, pattern="^paid_")); app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject|revoke)_")); app.add_handler(CallbackQueryHandler(my_profile, pattern="^my_profile$")); app.add_handler(CallbackQueryHandler(my_prefs, pattern="^my_prefs$")); app.add_handler(CallbackQueryHandler(back_home, pattern="^back_home$")); app.add_handler(CallbackQueryHandler(lambda u,c: show_menu(u,c,"Help: Find Match -> Pay -> Send Receipt -> Admin approves"), pattern="^help$"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    print("LoveConnect Professional Bot Running..."); app.run_polling()

if __name__ == "__main__": main()
