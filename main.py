import logging
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)

# ===================== CONFIG =====================
BOT_TOKEN = "8972509344:AAHlglMatOfgDDoPtWlQ0lZynb2a-VBI-z8"
ADMIN_ID = 8690101844
CHANNEL_ID = -1003953554451
CHANNEL_LINK = "https://t.me/mdsiddik90"

REFERRAL_COINS = 2        # প্রতি রেফারে কয়েন
COINS_PER_LINK = 3        # কত কয়েনে ১টি লিংক

# টপ পুরস্কার
TOP_REWARDS = {1: 12, 2: 6, 3: 3}
TOP_4_10_REWARD = 1

# Conversation states
WAITING_LINK_NAME = 1
WAITING_LINK_URL = 2
WAITING_BROADCAST = 3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================== DATABASE =====================
def init_db():
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            coins INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referred_by INTEGER,
            joined_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            created_at TEXT
        )
    """)
    c.execute("SELECT COUNT(*) FROM links")
    if c.fetchone()[0] == 0:
        default_links = [
            ("🔗@MissRose_bot", "https://mdsiddik998092-a11y.github.io/Cotall_bot/"),
            ("🔗 লিংক ২", "https://example.com/link2"),
            ("🔗 লিংক ৩", "https://example.com/link3"),
            ("🔗 লekke ৪", "https://example.com/link4"),
            ("🔗 লিংক ৫", "https://example.com/link5"),
        ]
        for name, url in default_links:
            c.execute("INSERT INTO links (name, url, created_at) VALUES (?, ?, ?)",
                      (name, url, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ----- Users -----
def get_user(user_id):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def add_user(user_id, username, full_name, referred_by=None):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO users (user_id, username, full_name, coins, referrals, referred_by, joined_at)
        VALUES (?, ?, ?, 0, 0, ?, ?)
    """, (user_id, username, full_name, referred_by, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_coins(user_id, amount):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def set_coins(user_id, amount):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("UPDATE users SET coins = ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def update_referrals(user_id):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_top_users(limit=10):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, coins, referrals FROM users ORDER BY referrals DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_users():
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, coins FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

# ----- Links -----
def get_all_links():
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT id, name, url FROM links ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return rows

def add_link(name, url):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("INSERT INTO links (name, url, created_at) VALUES (?, ?, ?)",
              (name, url, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def delete_link(link_id):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("DELETE FROM links WHERE id=?", (link_id,))
    conn.commit()
    conn.close()

def get_link_by_id(link_id):
    conn = sqlite3.connect("bot_data.db")
    c = conn.cursor()
    c.execute("SELECT id, name, url FROM links WHERE id=?", (link_id,))
    row = c.fetchone()
    conn.close()
    return row

# ===================== CHANNEL CHECK =====================
async def is_member(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ===================== MAIN MENU =====================
def main_menu_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("👤 প্রোফাইল", callback_data="profile"),
         InlineKeyboardButton("🔗 রেফার করুন", callback_data="refer")],
        [InlineKeyboardButton("🎉 Telegram bot ", callback_data="getlink"),
         InlineKeyboardButton("🏆 টপ ১০", callback_data="top10")],
        [InlineKeyboardButton("📢 চ্যানেল জয়েন করুন", url=CHANNEL_LINK)],
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ অ্যাডমিন প্যানেল", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

# ===================== /start =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0].split("_")[1])
        except:
            pass

    existing = get_user(user.id)
    if not existing:
        add_user(user.id, user.username or "", user.full_name, referred_by)
        if referred_by and referred_by != user.id:
            ref_user = get_user(referred_by)
            if ref_user:
                update_coins(referred_by, REFERRAL_COINS)
                update_referrals(referred_by)
                try:
                    await context.bot.send_message(
                        referred_by,
                        f"🎉 নতুন রেফার!\n"
                        f"👤 {user.full_name} আপনার লিংক দিয়ে যোগ দিয়েছে!\n"
                        f"💰 +{REFERRAL_COINS} কয়েন পেয়েছেন!"
                    )
                except:
                    pass

    if not await is_member(context.bot, user.id):
        keyboard = [
            [InlineKeyboardButton("📢 চ্যানেল জয়েন করুন", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ জয়েন করেছি", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "❌ বট ব্যবহার করতে প্রথমে আমাদের চ্যানেলে জয়েন করুন!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    links = get_all_links()
    await update.message.reply_text(
        f"👋 স্বাগতম, {user.full_name}!\n\n"
        f"🤖 এটি একটি রেফার বট।\n"
        f"💰 প্রতি রেফারে পাবেন: {REFERRAL_COINS} কয়েন\n"
        f"🔗 প্রতি {COINS_PER_LINK} কয়েনে পাবেন: ১টি বট\n"
        f"📦 বর্তমান টেলিগ্রাম বট : {len(links)}টি\n\n"
        f"নিচের মেনু থেকে শুরু করুন 👇",
        reply_markup=main_menu_keyboard(user.id)
    )

# ===================== CALLBACK HANDLER =====================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    # চ্যানেল চেক (check_join বাদে)
    if data != "check_join" and not await is_member(context.bot, user.id):
        keyboard = [
            [InlineKeyboardButton("📢 চ্যানেল জয়েন করুন", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ জয়েন করেছি", callback_data="check_join")]
        ]
        await query.edit_message_text(
            "❌ বট ব্যবহার করতে চ্যানেলে জয়েন করুন!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ---- চ্যানেল চেক ----
    if data == "check_join":
        if await is_member(context.bot, user.id):
            await query.edit_message_text(
                "✅ ধন্যবাদ! এখন বট ব্যবহার করুন।",
                reply_markup=main_menu_keyboard(user.id)
            )
        else:
            keyboard = [
                [InlineKeyboardButton("📢 চ্যানেল জয়েন করুন", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ জয়েন করেছি", callback_data="check_join")]
            ]
            await query.edit_message_text(
                "❌ আপনি এখনো চ্যানেলে জয়েন করেননি!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # ---- প্রোফাইল ----
    elif data == "profile":
        row = get_user(user.id)
        if not row:
            add_user(user.id, user.username or "", user.full_name)
            row = get_user(user.id)
        uid, uname, fname, coins, refs, ref_by, joined = row
        text = (
            f"👤 *প্রোফাইল*\n\n"
            f"🆔 আইডি: `{uid}`\n"
            f"📛 নাম: {fname}\n"
            f"💰 কয়েন: {coins}\n"
            f"👥 রেফার: {refs}\n"
            f"📅 যোগদান: {joined[:10]}"
        )
        keyboard = [[InlineKeyboardButton("🏠 হোম", callback_data="home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # ---- রেফার ----
    elif data == "refer":
        bot_me = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_me.username}?start=ref_{user.id}"
        row = get_user(user.id)
        coins = row[3] if row else 0
        refs = row[4] if row else 0
        text = (
            f"🔗 *আপনার রেফার লিংক:*\n`{ref_link}`\n\n"
            f"👥 মোট রেফার: {refs}\n"
            f"💰 মোট কয়েন: {coins}\n\n"
            f"প্রতি রেফারে পাবেন: {REFERRAL_COINS} কয়েন\n"
            f"এই লিংক শেয়ার করুন! 📤"
        )
        keyboard = [[InlineKeyboardButton("🏠 হোম", callback_data="home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # ---- লিংক কিনুন (লিংকের তালিকা দেখাও) ----
    elif data == "getlink":
        row = get_user(user.id)
        coins = row[3] if row else 0
        links = get_all_links()

        if not links:
            keyboard = [[InlineKeyboardButton("🏠 হোম", callback_data="home")]]
            await query.edit_message_text(
                "❌ এখন কোনো বট উপলব্ধ নেই!\nপরে আবার চেষ্টা করুন।",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # প্রতিটি লিংকের নাম বাটন হিসেবে দেখাও
        keyboard = []
        for lid, name, url in links:
            keyboard.append([
                InlineKeyboardButton(f"{name}", callback_data=f"buylink_{lid}")
            ])
        keyboard.append([InlineKeyboardButton("🏠 হোম", callback_data="home")])

        await query.edit_message_text(
            f"🎁 *বট  কিনুন*\n\n"
            f"💰 আপনার কয়েন: {coins}\n"
            f"💳 প্রতি ফাইল এর মূল্য: {COINS_PER_LINK} কয়েন\n\n"
            f"নিচে থেকে যে ফাইল কিনতে চান সেটিতে ক্লিক করুন 👇",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    # ---- নির্দিষ্ট লিংক কিনুন ----
    elif data.startswith("buylink_"):
        link_id = int(data.split("_")[1])
        link = get_link_by_id(link_id)

        if not link:
            await query.answer("❌ লিংকটি পাওয়া যায়নি!", show_alert=True)
            return

        row = get_user(user.id)
        coins = row[3] if row else 0

        if coins < COINS_PER_LINK:
            keyboard = [
                [InlineKeyboardButton("🔗 রেফার করুন", callback_data="refer")],
                [InlineKeyboardButton("◀️ ব্যাক", callback_data="getlink")]
            ]
            await query.edit_message_text(
                f"❌ *পর্যাপ্ত কয়েন নেই!*\n\n"
                f"💰 আপনার কয়েন: {coins}\n"
                f"💳 প্রয়োজন: {COINS_PER_LINK} কয়েন\n\n"
                f"রেফার করে কয়েন সংগ্রহ করুন!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return

        # কয়েন কাটুন
        update_coins(user.id, -COINS_PER_LINK)
        new_coins = coins - COINS_PER_LINK

        lid, name, url = link

        # প্রথম মেসেজ — কয়েন কাটার নিশ্চিতকরণ
        await query.edit_message_text(
            f"✅ *{COINS_PER_LINK} কয়েন কাটা হয়েছে!*\n\n"
            f"🔗 ফাইল : *{name}*\n"
            f"💰 বাকি কয়েন: {new_coins}\n\n"
            f"⏳ ২ সেকেন্ড পর আপনার ফাইলের লিংক পাঠানো হবে...",
            parse_mode="Markdown"
        )

        # ২ সেকেন্ড অপেক্ষা করুন
        await asyncio.sleep(1)

        # ✅ পরিবর্তন: লিংক এখন ক্লিকযোগ্য বাটন হিসেবে পাঠানো হবে
        keyboard = [
            [InlineKeyboardButton(f"🔗 {name} — এখানে ক্লিক করুন", url=url)],
            [InlineKeyboardButton("🏠 হোম", callback_data="home")]
        ]
        await context.bot.send_message(
            user.id,
            f"🎉 *আপনার বট ফাইল এসে গেছে!*\n\n"
            f"📦 *{name}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"নিচের বাটনে ক্লিক করলে সরাসরি ওয়েবসাইটে চলে যাবেন 👇\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    # ---- টপ ১০ ----
    elif data == "top10":
        tops = get_top_users(10)
        text = "🏆 *টপ ১০ রেফারকারী*\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, fname, coins, refs) in enumerate(tops, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            reward = TOP_REWARDS.get(i, TOP_4_10_REWARD)
            text += f"{medal} {fname}\n"
            text += f"   👥 রেফার: {refs} | 💰 কয়েন: {coins} | 🎁 পুরস্কার: {reward}\n\n"
        keyboard = [[InlineKeyboardButton("🏠 হোম", callback_data="home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # ---- হোম ----
    elif data == "home":
        await query.edit_message_text(
            "👋 স্বাগতম!\n\nনিচের মেনু থেকে বেছে নিন 👇",
            reply_markup=main_menu_keyboard(user.id)
        )

    # ==================== অ্যাডমিন ====================

    elif data == "admin_panel":
        if user.id != ADMIN_ID:
            await query.answer("❌ অ্যাডমিন নন!", show_alert=True)
            return
        users = get_all_users()
        links = get_all_links()
        keyboard = [
            [InlineKeyboardButton("👥 ইউজার ম্যানেজ", callback_data="admin_users"),
             InlineKeyboardButton("🔗 লিংক ম্যানেজ", callback_data="admin_links")],
            [InlineKeyboardButton("📊 পরিসংখ্যান", callback_data="admin_stats"),
             InlineKeyboardButton("🎁 পুরস্কার বিতরণ", callback_data="admin_reward")],
            [InlineKeyboardButton("📣 ব্রডকাস্ট", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🏠 হোম", callback_data="home")]
        ]
        await query.edit_message_text(
            f"⚙️ *অ্যাডমিন প্যানেল*\n\n"
            f"👥 মোট ইউজার: {len(users)}\n"
            f"🔗 মোট লিংক: {len(links)}\n\n"
            f"নিচে থেকে বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "admin_users":
        if user.id != ADMIN_ID:
            return
        users = get_all_users()
        keyboard = []
        for uid, fname, coins in users[:20]:
            keyboard.append([
                InlineKeyboardButton(f"👤 {fname[:15]} | 💰{coins}", callback_data=f"admin_user_{uid}")
            ])
        keyboard.append([InlineKeyboardButton("◀️ ব্যাক", callback_data="admin_panel")])
        await query.edit_message_text(
            f"👥 *ইউজার তালিকা* (মোট: {len(users)})\n\nইউজার বেছে নিন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "admin_links":
        if user.id != ADMIN_ID:
            return
        links = get_all_links()
        keyboard = []
        for lid, name, url in links:
            keyboard.append([
                InlineKeyboardButton(f"🗑️ {name}", callback_data=f"del_link_{lid}")
            ])
        keyboard.append([InlineKeyboardButton("➕ নতুন লিংক যোগ করুন", callback_data="add_link_start")])
        keyboard.append([InlineKeyboardButton("◀️ ব্যাক", callback_data="admin_panel")])

        text = f"🔗 *লিংক ম্যানেজমেন্ট* (মোট: {len(links)})\n\n"
        if links:
            for i, (lid, name, url) in enumerate(links, 1):
                text += f"{i}. *{name}*\n   `{url}`\n\n"
        else:
            text += "কোনো লিংক নেই।\n"
        text += "\n🗑️ মুছতে লিংকের উপর ক্লিক করুন"

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("del_link_"):
        if user.id != ADMIN_ID:
            return
        link_id = int(data.split("_")[2])
        link = get_link_by_id(link_id)
        if link:
            keyboard = [
                [InlineKeyboardButton("✅ হ্যাঁ, মুছুন", callback_data=f"confirm_del_{link_id}"),
                 InlineKeyboardButton("❌ বাতিল", callback_data="admin_links")]
            ]
            await query.edit_message_text(
                f"⚠️ *নিশ্চিত করুন*\n\n"
                f"এই লিংক মুছবেন?\n\n"
                f"নাম: *{link[1]}*\n"
                f"URL: `{link[2]}`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

    elif data.startswith("confirm_del_"):
        if user.id != ADMIN_ID:
            return
        link_id = int(data.split("_")[2])
        delete_link(link_id)
        await query.answer("✅ লিংক মুছে ফেলা হয়েছে!", show_alert=True)
        links = get_all_links()
        keyboard = []
        for lid, name, url in links:
            keyboard.append([
                InlineKeyboardButton(f"🗑️ {name}", callback_data=f"del_link_{lid}")
            ])
        keyboard.append([InlineKeyboardButton("➕ নতুন লিংক যোগ করুন", callback_data="add_link_start")])
        keyboard.append([InlineKeyboardButton("◀️ ব্যাক", callback_data="admin_panel")])

        text = f"🔗 *লিংক ম্যানেজমেন্ট* (মোট: {len(links)})\n\n"
        if links:
            for i, (lid, name, url) in enumerate(links, 1):
                text += f"{i}. *{name}*\n   `{url}`\n\n"
        else:
            text += "কোনো লিংক নেই।\n"
        text += "\n🗑️ মুছতে লিংকের উপর ক্লিক করুন"

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "add_link_start":
        if user.id != ADMIN_ID:
            return
        context.user_data["adding_link"] = True
        keyboard = [[InlineKeyboardButton("❌ বাতিল", callback_data="cancel_add_link")]]
        await query.edit_message_text(
            "➕ *নতুন লিংক যোগ করুন*\n\n"
            "প্রথমে লিংকের *নাম* লিখুন:\n"
            "(উদাহরণ: 🔗 আমার লিংক)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["link_step"] = "name"

    elif data == "cancel_add_link":
        if user.id != ADMIN_ID:
            return
        context.user_data.pop("adding_link", None)
        context.user_data.pop("link_step", None)
        context.user_data.pop("new_link_name", None)
        links = get_all_links()
        keyboard = []
        for lid, name, url in links:
            keyboard.append([
                InlineKeyboardButton(f"🗑️ {name}", callback_data=f"del_link_{lid}")
            ])
        keyboard.append([InlineKeyboardButton("➕ নতুন লিংক যোগ করুন", callback_data="add_link_start")])
        keyboard.append([InlineKeyboardButton("◀️ ব্যাক", callback_data="admin_panel")])
        await query.edit_message_text(
            f"🔗 *লিংক ম্যানেজমেন্ট* (মোট: {len(links)})\n\n🗑️ মুছতে লিংকের উপর ক্লিক করুন",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "admin_stats":
        if user.id != ADMIN_ID:
            return
        users = get_all_users()
        total_coins = sum(c for _, _, c in users)
        links = get_all_links()
        tops = get_top_users(3)
        keyboard = [[InlineKeyboardButton("◀️ ব্যাক", callback_data="admin_panel")]]
        text = (
            f"📊 *পরিসংখ্যান*\n\n"
            f"👥 মোট ইউজার: {len(users)}\n"
            f"💰 মোট কয়েন (সব): {total_coins}\n"
            f"🔗 মোট ফাইল: {len(links)}\n\n"
            f"🏆 *টপ ৩:*\n"
        )
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, fname, coins, refs) in enumerate(tops, 1):
            text += f"{medals[i-1]} {fname} — {refs} রেফার\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "admin_reward":
        if user.id != ADMIN_ID:
            return
        tops = get_top_users(10)
        distributed = []
        for i, (uid, fname, coins, refs) in enumerate(tops, 1):
            reward = TOP_REWARDS.get(i, TOP_4_10_REWARD)
            update_coins(uid, reward)
            distributed.append(f"{i}. {fname} → +{reward} কয়েন")
            try:
                await context.bot.send_message(uid, f"🎁 আপনি টপ {i} হয়েছেন! +{reward} কয়েন পুরস্কার পেয়েছেন!")
            except:
                pass
        text = "✅ *পুরস্কার বিতরণ সম্পন্ন!*\n\n" + "\n".join(distributed)
        keyboard = [[InlineKeyboardButton("◀️ ব্যাক", callback_data="admin_panel")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "admin_broadcast":
        if user.id != ADMIN_ID:
            return
        keyboard = [[InlineKeyboardButton("❌ বাতিল", callback_data="admin_panel")]]
        await query.edit_message_text(
            "📣 *ব্রডকাস্ট মেসেজ*\n\n"
            "সকল ইউজারকে যে মেসেজ পাঠাতে চান তা লিখুন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["broadcasting"] = True

    elif data.startswith("admin_user_"):
        if user.id != ADMIN_ID:
            return
        target_id = int(data.split("_")[2])
        row = get_user(target_id)
        if not row:
            await query.answer("ইউজার পাওয়া যায়নি!", show_alert=True)
            return
        uid, uname, fname, coins, refs, ref_by, joined = row
        keyboard = [
            [InlineKeyboardButton("➕ ১০", callback_data=f"coin_add_{target_id}_10"),
             InlineKeyboardButton("➕ ৫০", callback_data=f"coin_add_{target_id}_50"),
             InlineKeyboardButton("➕ ১০০", callback_data=f"coin_add_{target_id}_100")],
            [InlineKeyboardButton("➖ ১০", callback_data=f"coin_sub_{target_id}_10"),
             InlineKeyboardButton("➖ ৫০", callback_data=f"coin_sub_{target_id}_50"),
             InlineKeyboardButton("➖ ১০০", callback_data=f"coin_sub_{target_id}_100")],
            [InlineKeyboardButton("◀️ ব্যাক", callback_data="admin_users")]
        ]
        await query.edit_message_text(
            f"👤 *{fname}*\n"
            f"🆔 আইডি: {uid}\n"
            f"💰 কয়েন: {coins}\n"
            f"👥 রেফার: {refs}\n"
            f"📅 যোগদান: {joined[:10]}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("coin_add_"):
        if user.id != ADMIN_ID:
            return
        parts = data.split("_")
        target_id = int(parts[2])
        amount = int(parts[3])
        update_coins(target_id, amount)
        row = get_user(target_id)
        await query.answer(f"✅ +{amount} কয়েন যোগ হয়েছে!", show_alert=True)
        keyboard = [
            [InlineKeyboardButton("➕ ১০", callback_data=f"coin_add_{target_id}_10"),
             InlineKeyboardButton("➕ ৫০", callback_data=f"coin_add_{target_id}_50"),
             InlineKeyboardButton("➕ ১০০", callback_data=f"coin_add_{target_id}_100")],
            [InlineKeyboardButton("➖ ১০", callback_data=f"coin_sub_{target_id}_10"),
             InlineKeyboardButton("➖ ৫০", callback_data=f"coin_sub_{target_id}_50"),
             InlineKeyboardButton("➖ ১০০", callback_data=f"coin_sub_{target_id}_100")],
            [InlineKeyboardButton("◀️ ব্যাক", callback_data="admin_users")]
        ]
        await query.edit_message_text(
            f"👤 *{row[2]}*\n🆔 {target_id}\n💰 কয়েন: {row[3]}\n👥 রেফার: {row[4]}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("coin_sub_"):
        if user.id != ADMIN_ID:
            return
        parts = data.split("_")
        target_id = int(parts[2])
        amount = int(parts[3])
        row = get_user(target_id)
        new_coins = max(0, row[3] - amount)
        set_coins(target_id, new_coins)
        row = get_user(target_id)
        await query.answer(f"✅ -{amount} কয়েন কমানো হয়েছে!", show_alert=True)
        keyboard = [
            [InlineKeyboardButton("➕ ১০", callback_data=f"coin_add_{target_id}_10"),
             InlineKeyboardButton("➕ ৫০", callback_data=f"coin_add_{target_id}_50"),
             InlineKeyboardButton("➕ ১০০", callback_data=f"coin_add_{target_id}_100")],
            [InlineKeyboardButton("➖ ১০", callback_data=f"coin_sub_{target_id}_10"),
             InlineKeyboardButton("➖ ৫০", callback_data=f"coin_sub_{target_id}_50"),
             InlineKeyboardButton("➖ ১০০", callback_data=f"coin_sub_{target_id}_100")],
            [InlineKeyboardButton("◀️ ব্যাক", callback_data="admin_users")]
        ]
        await query.edit_message_text(
            f"👤 *{row[2]}*\n🆔 {target_id}\n💰 কয়েন: {row[3]}\n👥 রেফার: {row[4]}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ===================== MESSAGE HANDLER =====================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if user.id == ADMIN_ID and context.user_data.get("adding_link"):
        step = context.user_data.get("link_step")

        if step == "name":
            context.user_data["new_link_name"] = text
            context.user_data["link_step"] = "url"
            keyboard = [[InlineKeyboardButton("❌ বাতিল", callback_data="cancel_add_link")]]
            await update.message.reply_text(
                f"✅ নাম সেট: *{text}*\n\n"
                f"এখন লিংকের *URL* লিখুন:\n"
                f"(উদাহরণ: https://example.com)",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

        elif step == "url":
            name = context.user_data.get("new_link_name", "নতুন লিংক")
            url = text.strip()

            if not (url.startswith("http://") or url.startswith("https://")):
                await update.message.reply_text(
                    "❌ সঠিক URL দিন! http:// বা https:// দিয়ে শুরু করুন।"
                )
                return

            add_link(name, url)
            context.user_data.pop("adding_link", None)
            context.user_data.pop("link_step", None)
            context.user_data.pop("new_link_name", None)

            links = get_all_links()
            keyboard = [
                [InlineKeyboardButton("🔗 লিংক ম্যানেজ", callback_data="admin_links")],
                [InlineKeyboardButton("🏠 হোম", callback_data="home")]
            ]
            await update.message.reply_text(
                f"✅ *লিংক সফলভাবে যোগ হয়েছে!*\n\n"
                f"📛 নাম: {name}\n"
                f"🔗 URL: `{url}`\n\n"
                f"মোট ফাইল  এখন: {len(links)}টি",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

    elif user.id == ADMIN_ID and context.user_data.get("broadcasting"):
        context.user_data.pop("broadcasting", None)
        users = get_all_users()
        sent = 0
        failed = 0
        for uid, _, _ in users:
            try:
                await context.bot.send_message(uid, text)
                sent += 1
            except:
                failed += 1

        keyboard = [[InlineKeyboardButton("◀️ অ্যাডমিন প্যানেল", callback_data="admin_panel")]]
        await update.message.reply_text(
            f"✅ *ব্রডকাস্ট সম্পন্ন!*\n\n"
            f"📤 পাঠানো হয়েছে: {sent} জনকে\n"
            f"❌ ব্যর্থ: {failed} জন",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ===================== ADMIN COMMANDS =====================
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("ব্যবহার: /broadcast <মেসেজ>")
        return
    msg = " ".join(context.args)
    users = get_all_users()
    sent = 0
    for uid, _, _ in users:
        try:
            await context.bot.send_message(uid, msg)
            sent += 1
        except:
            pass
    await update.message.reply_text(f"✅ {sent} জনের কাছে মেসেজ পাঠানো হয়েছে!")

async def give_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    tops = get_top_users(10)
    for i, (uid, fname, coins, refs) in enumerate(tops, 1):
        reward = TOP_REWARDS.get(i, TOP_4_10_REWARD)
        update_coins(uid, reward)
        try:
            await context.bot.send_message(uid, f"🏆 টপ {i}! পুরস্কার: +{reward} কয়েন!")
        except:
            pass
    await update.message.reply_text("✅ পুরস্কার বিতরণ সম্পন্ন!")

async def addlink_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("ব্যবহার: /addlink লিংকের নাম | https://example.com")
        return
    full_text = " ".join(context.args)
    if "|" not in full_text:
        await update.message.reply_text("ব্যবহার: /addlink লিংকের নাম | https://example.com")
        return
    parts = full_text.split("|", 1)
    name = parts[0].strip()
    url = parts[1].strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ সঠিক URL দিন!")
        return
    add_link(name, url)
    links = get_all_links()
    await update.message.reply_text(
        f"✅ লিংক যোগ হয়েছে!\n\nনাম: {name}\nURL: {url}\n\nমোট লিংক: {len(links)}টি"
    )

async def listlinks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    links = get_all_links()
    if not links:
        await update.message.reply_text("কোনো লিংক নেই।")
        return
    text = f"🔗 *সব লিংক ({len(links)}টি):*\n\n"
    for lid, name, url in links:
        text += f"🆔 {lid}. *{name}*\n`{url}`\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def dellink_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("ব্যবহার: /dellink <লিংক আইডি>\nআইডি দেখতে /listlinks")
        return
    try:
        link_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ সঠিক আইডি দিন!")
        return
    link = get_link_by_id(link_id)
    if not link:
        await update.message.reply_text("❌ লিংক পাওয়া যায়নি!")
        return
    delete_link(link_id)
    await update.message.reply_text(f"✅ লিংক মুছে ফেলা হয়েছে!\nনাম: {link[1]}")

# ===================== MAIN =====================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("reward", give_reward))
    app.add_handler(CommandHandler("addlink", addlink_cmd))
    app.add_handler(CommandHandler("listlinks", listlinks_cmd))
    app.add_handler(CommandHandler("dellink", dellink_cmd))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("✅ বট চালু হচ্ছে...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
