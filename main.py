# main.py
# pip install pyTelegramBotAPI

import sqlite3
import time
from typing import Optional, Dict, List
from telebot import TeleBot, types

# =======================
# CONFIG
# =======================
TOKEN = "8061624031:AAG5LQ1tHO4V8hkh8egQDdZfgW2zy3X5jAo"
ADMIN_ID = 5815294733

PAYMENT_REKV = {
    "visa": "💳 VISA/UZCARD" "hozir bu kartalar ishlamayapti Humo tugmasin bosing !",
    "humo": "🟦 HUMO rekvizit:\n\nIsm: \nBank: Humo",
    "crypto": "hozir bu kartalar ishlamayapti Humo tugmasin bosing !",
}

REF_BONUS_PERCENT = 3      # referal bonus (depozitdan %)
MIN_DEPOSIT = 1000         # minimal depozit

WEAR_LIST = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]

# 2 bosqichli katalog: Bo'lim -> Qurollar
CATEGORIES: Dict[str, List[str]] = {
    "🔪 Knives": [
        "Bayonet", "Flip Knife", "Gut Knife", "Karambit", "M9 Bayonet", "Huntsman Knife",
        "Falchion Knife", "Bowie Knife", "Butterfly Knife", "Shadow Daggers", "Navaja Knife",
        "Stiletto Knife", "Ursus Knife", "Talon Knife", "Classic Knife", "Paracord Knife",
        "Survival Knife", "Nomad Knife", "Skeleton Knife", "Kukri Knife"
    ],
    "🧤 Gloves": [
        "Sport Gloves", "Driver Gloves", "Hand Wraps", "Moto Gloves", "Specialist Gloves",
        "Hydra Gloves", "Broken Fang Gloves"
    ],
    "🔫 Pistols": [
        "Glock-18", "USP-S", "P2000", "P250", "Five-SeveN", "Tec-9", "CZ75-Auto",
        "Dual Berettas", "Desert Eagle", "R8 Revolver"
    ],
    "🔫 SMG": [
        "MAC-10", "MP9", "MP7", "MP5-SD", "UMP-45", "P90", "PP-Bizon"
    ],
    "🔫 Rifles": [
        "AK-47", "M4A4", "M4A1-S", "FAMAS", "Galil AR", "SG 553", "AUG"
    ],
    "🎯 Snipers": [
        "AWP", "SSG 08", "SCAR-20", "G3SG1"
    ],
    "💥 Heavy": [
        "Nova", "XM1014", "MAG-7", "Sawed-Off", "M249", "Negev"
    ],
    "⚡ Equipment": [
        "Zeus x27"
    ]
}

DB = "cs2_shop.db"
bot = TeleBot(TOKEN)

# =======================
# DB
# =======================
def db():
    return sqlite3.connect(DB, check_same_thread=False)

def col_exists(table: str, col: str) -> bool:
    con = db()
    cur = con.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    con.close()
    return col in cols

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        referred_by INTEGER,
        created_at INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section TEXT NOT NULL,         -- "🔫 Rifles"
        weapon TEXT NOT NULL,          -- "AK-47"
        title TEXT NOT NULL,           -- skin nomi
        price INTEGER NOT NULL,
        wear TEXT NOT NULL,
        used_note TEXT,
        photo_url TEXT,
        description TEXT,
        active INTEGER DEFAULT 1,
        created_at INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        created_at INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',  -- pending/approved/rejected/delivered
        trade_link TEXT,
        admin_note TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS deposits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        method TEXT NOT NULL, -- visa/humo/crypto
        status TEXT NOT NULL DEFAULT 'waiting_receipt', -- waiting_receipt/submitted/approved/rejected
        created_at INTEGER NOT NULL,
        receipt_file_id TEXT,
        admin_note TEXT
    )
    """)

    con.commit()
    con.close()

    # Migration (eski DB bo'lsa)
    if not col_exists("orders", "trade_link"):
        con = db()
        cur = con.cursor()
        cur.execute("ALTER TABLE orders ADD COLUMN trade_link TEXT")
        con.commit()
        con.close()

init_db()

# =======================
# STATE
# =======================
state = {}  # uid -> {"step": "...", "data": {...}}

def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

def ensure_user(u):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (u.id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users(user_id, username, balance, referred_by, created_at) VALUES(?,?,?,?,?)",
            (u.id, u.username or "", 0, None, int(time.time()))
        )
    else:
        cur.execute("UPDATE users SET username=? WHERE user_id=?", (u.username or "", u.id))
    con.commit()
    con.close()

def get_balance(uid: int) -> int:
    con = db()
    cur = con.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    con.close()
    return int(r[0]) if r else 0

def add_balance(uid: int, amount: int):
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
    con.commit()
    con.close()

def set_referred_by(uid: int, ref_uid: int):
    if uid == ref_uid:
        return
    con = db()
    cur = con.cursor()
    cur.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    if r and r[0] is None:
        cur.execute("UPDATE users SET referred_by=? WHERE user_id=?", (ref_uid, uid))
        con.commit()
    con.close()

def get_referred_by(uid: int) -> Optional[int]:
    con = db()
    cur = con.cursor()
    cur.execute("SELECT referred_by FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    con.close()
    return r[0] if r else None

# =======================
# KEYBOARDS
# =======================
def main_menu(uid: int):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛒 Katalog", "💰 Balans")
    kb.add("➕ Hisob to‘ldirish", "🎁 Bonus & Referal")
    kb.add("🧾 Buyurtmalarim", "💬 Admin bilan aloqa")
    if is_admin(uid):
        kb.add("🛠 Admin panel")
    return kb

def admin_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Skin qo‘shish", "📦 Buyurtmalar")
    kb.add("💳 Depozitlar", "📦 Mahsulotlar")
    kb.add("⬅️ Orqaga")
    return kb

def sections_kb(prefix: str):
    ikb = types.InlineKeyboardMarkup()
    for sec in CATEGORIES.keys():
        ikb.add(types.InlineKeyboardButton(sec, callback_data=f"{prefix}:{sec}"))
    return ikb

def weapons_kb(prefix: str, section: str):
    ikb = types.InlineKeyboardMarkup()
    for w in CATEGORIES.get(section, []):
        ikb.add(types.InlineKeyboardButton(w, callback_data=f"{prefix}:{w}"))
    ikb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data=f"backsec:{prefix}"))
    return ikb

def wear_kb():
    ikb = types.InlineKeyboardMarkup()
    for w in WEAR_LIST:
        ikb.add(types.InlineKeyboardButton(w, callback_data=f"wear:{w}"))
    return ikb

# =======================
# START + REFERAL
# =======================
@bot.message_handler(commands=["start"])
def start(m):
    ensure_user(m.from_user)

    parts = (m.text or "").split()
    if len(parts) >= 2 and parts[1].startswith("ref_"):
        try:
            ref_uid = int(parts[1].replace("ref_", "").strip())
            dummy = types.SimpleNamespace(id=ref_uid, username="")
            ensure_user(dummy)
            set_referred_by(m.from_user.id, ref_uid)
        except:
            pass

    bot.send_message(
        m.chat.id,
        "✅ CS2 Skin Do‘kon botiga xush kelibsiz!\n\n"
        "🛒 Katalogdan skin tanlang.\n"
        "➕ Hisob to‘ldirish orqali balans qo‘shing.",
        reply_markup=main_menu(m.from_user.id)
    )

# =======================
# USER: BALANCE / REFERAL / CONTACT
# =======================
@bot.message_handler(func=lambda m: m.text == "💰 Balans")
def balance(m):
    ensure_user(m.from_user)
    bot.send_message(m.chat.id, f"💰 Balansingiz: {get_balance(m.from_user.id)} so‘m", reply_markup=main_menu(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "🎁 Bonus & Referal")
def bonus_ref(m):
    ensure_user(m.from_user)
    me = bot.get_me().username
    link = f"https://t.me/{me}?start=ref_{m.from_user.id}"
    bot.send_message(
        m.chat.id,
        f"🎁 Referal:\nDo‘stingiz depozit qilsa sizga {REF_BONUS_PERCENT}% bonus tushadi.\n\n🔗 Link:\n{link}"
    )

@bot.message_handler(func=lambda m: m.text == "💬 Admin bilan aloqa")
def contact(m):
    state[m.from_user.id] = {"step": "forward_admin", "data": {}}
    bot.send_message(m.chat.id, "Xabaringizni yozing — adminga yuboraman.")

@bot.message_handler(func=lambda m: state.get(m.from_user.id, {}).get("step") == "forward_admin", content_types=["text"])
def forward_admin(m):
    bot.forward_message(ADMIN_ID, m.chat.id, m.message_id)
    bot.send_message(m.chat.id, "✅ Xabaringiz adminga yuborildi.", reply_markup=main_menu(m.from_user.id))
    state.pop(m.from_user.id, None)

# =======================
# USER: CATALOG (section -> weapon -> products)
# =======================
@bot.message_handler(func=lambda m: m.text == "🛒 Katalog")
def catalog(m):
    bot.send_message(m.chat.id, "📂 Bo‘lim tanlang:", reply_markup=sections_kb("sec"))

@bot.callback_query_handler(func=lambda c: c.data.startswith("sec:"))
def section_pick(c):
    section = c.data.split(":", 1)[1]
    # save section for this message flow (optional)
    bot.edit_message_text(
        f"{section}\n\n🔫 Qurol tanlang:",
        c.message.chat.id,
        c.message.message_id,
        reply_markup=weapons_kb("wep", section)
    )
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("backsec:"))
def back_to_sections(c):
    # backsec:wep or backsec:addwep
    bot.edit_message_text(
        "📂 Bo‘lim tanlang:",
        c.message.chat.id,
        c.message.message_id,
        reply_markup=sections_kb("sec")
    )
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("wep:"))
def weapon_pick(c):
    weapon = c.data.split(":", 1)[1]

    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT id, title, price, wear
        FROM products
        WHERE active=1 AND weapon=?
        ORDER BY id DESC
        LIMIT 25
    """, (weapon,))
    rows = cur.fetchall()
    con.close()

    ikb = types.InlineKeyboardMarkup()
    if not rows:
        ikb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="backsec:wep"))
        bot.edit_message_text(f"📌 {weapon} bo‘limida hozircha skin yo‘q.", c.message.chat.id, c.message.message_id, reply_markup=ikb)
        bot.answer_callback_query(c.id)
        return

    for pid, title, price, wear in rows:
        ikb.add(types.InlineKeyboardButton(f"{title} ({wear}) — {price} so‘m", callback_data=f"p:{pid}"))
    ikb.add(types.InlineKeyboardButton("⬅️ Bo‘limlar", callback_data="backsec:wep"))

    bot.edit_message_text(f"🧩 {weapon} — skin tanlang:", c.message.chat.id, c.message.message_id, reply_markup=ikb)
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("p:"))
def product_view(c):
    pid = int(c.data.split(":", 1)[1])
    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT section, weapon, title, price, wear, used_note, photo_url, description
        FROM products WHERE id=? AND active=1
    """, (pid,))
    r = cur.fetchone()
    con.close()

    if not r:
        bot.answer_callback_query(c.id, "Topilmadi.")
        return

    section, weapon, title, price, wear, used_note, photo_url, desc = r
    txt = (
        f"🧩 *{title}*\n"
        f"📂 {section}\n"
        f"🔫 {weapon}\n"
        f"✨ Holati: {wear}\n"
        f"🕒 Ishlatilgani: {used_note or 'ko‘rsatilmagan'}\n"
        f"💰 Narx: {price} so‘m\n\n"
        f"{desc or ''}\n\n"
        f"✅ Sotib olish uchun davom etamizmi?"
    )

    ikb = types.InlineKeyboardMarkup()
    ikb.add(types.InlineKeyboardButton("✅ Sotib olish", callback_data=f"buy:{pid}"))
    ikb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="backsec:wep"))

    if photo_url:
        bot.send_photo(c.message.chat.id, photo_url, caption=txt, parse_mode="Markdown", reply_markup=ikb)
    else:
        bot.send_message(c.message.chat.id, txt, parse_mode="Markdown", reply_markup=ikb)

    bot.answer_callback_query(c.id)

# =======================
# BUY FLOW: trade link -> admin approve/reject/delivered
# =======================
@bot.callback_query_handler(func=lambda c: c.data.startswith("buy:"))
def buy_start(c):
    uid = c.from_user.id
    pid = int(c.data.split(":", 1)[1])
    ensure_user(c.from_user)

    con = db()
    cur = con.cursor()
    cur.execute("SELECT price, title FROM products WHERE id=? AND active=1", (pid,))
    pr = cur.fetchone()
    con.close()

    if not pr:
        bot.answer_callback_query(c.id, "Mahsulot topilmadi.")
        return

    price, title = int(pr[0]), pr[1]
    bal = get_balance(uid)
    if bal < price:
        bot.answer_callback_query(c.id, "Balans yetarli emas.")
        bot.send_message(c.message.chat.id, f"❗ Balans yetarli emas.\nKerak: {price} so‘m\nSizda: {bal} so‘m\n\n➕ Hisob to‘ldiring.")
        return

    # order yaratamiz (balans hozircha yechilmaydi)
    con = db()
    cur = con.cursor()
    cur.execute("INSERT INTO orders(user_id, product_id, created_at, status) VALUES(?,?,?,?)",
                (uid, pid, int(time.time()), "pending"))
    oid = cur.lastrowid
    con.commit()
    con.close()

    state[uid] = {"step": "order_trade", "data": {"order_id": oid}}
    bot.answer_callback_query(c.id, "Buyurtma yaratildi!")
    bot.send_message(
        c.message.chat.id,
        f"✅ Buyurtma #{oid} yaratildi.\n\n"
        f"Endi Steam *Trade Link* yuboring:\n"
        f"Misol: https://steamcommunity.com/tradeoffer/new/?partner=XXXX&token=YYYY",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: state.get(m.from_user.id, {}).get("step") == "order_trade", content_types=["text"])
def order_trade_link(m):
    uid = m.from_user.id
    trade = (m.text or "").strip()

    if "steamcommunity.com/tradeoffer/new" not in trade:
        bot.send_message(m.chat.id, "❗ Trade link xato ko‘rinadi. To‘g‘ri trade link yuboring.")
        return

    oid = state[uid]["data"]["order_id"]

    con = db()
    cur = con.cursor()
    cur.execute("UPDATE orders SET trade_link=? WHERE id=? AND user_id=?", (trade, oid, uid))

    cur.execute("""
        SELECT p.title, p.price, p.weapon
        FROM orders o JOIN products p ON p.id=o.product_id
        WHERE o.id=?
    """, (oid,))
    title, price, weapon = cur.fetchone()
    con.commit()
    con.close()

    # admin buttons
    ikb = types.InlineKeyboardMarkup()
    ikb.add(
        types.InlineKeyboardButton("✅ Tasdiq (balans yechadi)", callback_data=f"ordok:{oid}"),
        types.InlineKeyboardButton("❌ Rad", callback_data=f"ordno:{oid}")
    )

    bot.send_message(
        ADMIN_ID,
        f"🆕 Buyurtma #{oid}\n"
        f"User: @{m.from_user.username} ({uid})\n"
        f"Mahsulot: {title}\n"
        f"Qurol: {weapon}\n"
        f"Narx: {price} so‘m\n\n"
        f"Trade link:\n{trade}",
        reply_markup=ikb
    )

    bot.send_message(m.chat.id, "✅ Trade link qabul qilindi. Admin tekshiradi.")
    state.pop(uid, None)

@bot.callback_query_handler(func=lambda c: c.data.startswith(("ordok:", "ordno:", "orddel:")))
def order_admin_decision(c):
    if not is_admin(c.from_user.id):
        return

    action, oid = c.data.split(":")
    oid = int(oid)

    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT o.user_id, o.status, o.trade_link, p.price, p.title
        FROM orders o JOIN products p ON p.id=o.product_id
        WHERE o.id=?
    """, (oid,))
    r = cur.fetchone()
    if not r:
        con.close()
        bot.answer_callback_query(c.id, "Topilmadi.")
        return

    user_id, status, trade_link, price, title = r
    price = int(price)

    # ✅ TASDIQ: pending -> approved va balans yechiladi
    if action == "ordok":
        if status != "pending":
            con.close()
            bot.answer_callback_query(c.id, "Allaqachon yakunlangan.")
            return

        cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        bal = int(cur.fetchone()[0])
        if bal < price:
            cur.execute("UPDATE orders SET status=?, admin_note=? WHERE id=?", ("rejected", "Balans yetmadi", oid))
            con.commit()
            con.close()
            bot.send_message(user_id, f"❌ Buyurtma #{oid} rad etildi: balans yetarli emas.")
            bot.answer_callback_query(c.id, "Balans yetmadi.")
            bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
            return

        cur.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (price, user_id))
        cur.execute("UPDATE orders SET status=? WHERE id=?", ("approved", oid))
        con.commit()
        con.close()

        # Endi admin xabarda faqat "Trade yuborildi" qolsin
        ikb = types.InlineKeyboardMarkup()
        ikb.add(types.InlineKeyboardButton("📤 Trade yuborildi (delivered)", callback_data=f"orddel:{oid}"))
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=ikb)

        bot.send_message(
            user_id,
            f"✅ Buyurtma #{oid} tasdiqlandi!\n"
            f"Mahsulot: {title}\n"
            f"💰 -{price} so‘m\n\n"
            f"Admin Steam’dan trade yuboradi.\n"
            f"Trade link: {trade_link}"
        )
        bot.answer_callback_query(c.id, "Tasdiqlandi!")
        return

    # ❌ RAD: pending -> rejected
    if action == "ordno":
        if status != "pending":
            con.close()
            bot.answer_callback_query(c.id, "Allaqachon yakunlangan.")
            return
        cur.execute("UPDATE orders SET status=? WHERE id=?", ("rejected", oid))
        con.commit()
        con.close()
        bot.send_message(user_id, f"❌ Buyurtma #{oid} rad etildi.\nAdmin bilan bog‘laning.")
        bot.answer_callback_query(c.id, "Rad etildi.")
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
        return

    # 📤 DELIVERED: approved -> delivered
    if action == "orddel":
        if status != "approved":
            con.close()
            bot.answer_callback_query(c.id, "Avval tasdiqlanishi kerak.")
            return
        cur.execute("UPDATE orders SET status=? WHERE id=?", ("delivered", oid))
        con.commit()
        con.close()
        bot.send_message(
            user_id,
            f"📤 Buyurtma #{oid}: Trade yuborildi ✅\n"
            f"Agar 10 daqiqada kelmasa, admin bilan bog‘laning."
        )
        bot.answer_callback_query(c.id, "Delivered!")
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
        return

# =======================
# USER: Orders list
# =======================
@bot.message_handler(func=lambda m: m.text == "🧾 Buyurtmalarim")
def my_orders(m):
    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT o.id, o.status, p.title
        FROM orders o JOIN products p ON p.id=o.product_id
        WHERE o.user_id=?
        ORDER BY o.id DESC LIMIT 10
    """, (m.from_user.id,))
    rows = cur.fetchall()
    con.close()

    if not rows:
        bot.send_message(m.chat.id, "Hozircha buyurtmangiz yo‘q.")
        return

    msg = "🧾 Oxirgi buyurtmalar:\n"
    for oid, stt, title in rows:
        msg += f"#{oid} — {title} — *{stt}*\n"
    bot.send_message(m.chat.id, msg, parse_mode="Markdown")

# =======================
# DEPOSIT: amount -> method -> paid(btn disappears) -> receipt -> admin approve/reject
# =======================
@bot.message_handler(func=lambda m: m.text == "➕ Hisob to‘ldirish")
def dep_start(m):
    ensure_user(m.from_user)
    state[m.from_user.id] = {"step": "dep_amount", "data": {}}
    bot.send_message(m.chat.id, f"💳 Qancha to‘ldirmoqchisiz? (son, so‘m)\nMinimal: {MIN_DEPOSIT}")

@bot.message_handler(func=lambda m: state.get(m.from_user.id, {}).get("step") == "dep_amount", content_types=["text"])
def dep_amount(m):
    txt = (m.text or "").strip()
    if not txt.isdigit():
        bot.send_message(m.chat.id, "❗ Faqat son kiriting. Masalan: 50000")
        return
    amount = int(txt)
    if amount < MIN_DEPOSIT:
        bot.send_message(m.chat.id, f"❗ Minimal summa: {MIN_DEPOSIT} so‘m")
        return

    st = state[m.from_user.id]
    st["data"]["amount"] = amount
    st["step"] = "dep_method"

    ikb = types.InlineKeyboardMarkup()
    ikb.add(
        types.InlineKeyboardButton("💳 Visa/Uzcard", callback_data="dep:visa"),
        types.InlineKeyboardButton("🟦 Humo", callback_data="dep:humo")
    )
    ikb.add(types.InlineKeyboardButton("₿ Kripto", callback_data="dep:crypto"))
    bot.send_message(m.chat.id, f"✅ Summa: {amount} so‘m\nUsul tanlang:", reply_markup=ikb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("dep:"))
def dep_method(c):
    uid = c.from_user.id
    st = state.get(uid)
    if not st or st.get("step") != "dep_method":
        bot.answer_callback_query(c.id, "Sessiya yo‘q. Qayta urinib ko‘ring.")
        return

    method = c.data.split(":", 1)[1]
    amount = st["data"]["amount"]

    con = db()
    cur = con.cursor()
    cur.execute("INSERT INTO deposits(user_id, amount, method, status, created_at) VALUES(?,?,?,?,?)",
                (uid, amount, method, "waiting_receipt", int(time.time())))
    dep_id = cur.lastrowid
    con.commit()
    con.close()

    st["data"]["dep_id"] = dep_id
    st["data"]["method"] = method
    st["step"] = "dep_wait_paid"

    info = PAYMENT_REKV.get(method, "Rekvizit topilmadi.")
    text = f"{info}\n\n✅ To‘ldirish: {amount} so‘m\n\nPul yuboring, so‘ng *To‘lov qildim* ni bosing."
    ikb = types.InlineKeyboardMarkup()
    ikb.add(types.InlineKeyboardButton("✅ To‘lov qildim", callback_data=f"paid:{dep_id}"))

    bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="Markdown", reply_markup=ikb)
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("paid:"))
def dep_paid(c):
    uid = c.from_user.id
    dep_id = int(c.data.split(":", 1)[1])
    st = state.get(uid)

    if not st or st.get("step") != "dep_wait_paid" or st["data"].get("dep_id") != dep_id:
        bot.answer_callback_query(c.id, "Sessiya mos emas.")
        return

    # tugma yo'qolsin
    bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)

    # status submitted
    con = db()
    cur = con.cursor()
    cur.execute("UPDATE deposits SET status=? WHERE id=? AND user_id=?", ("submitted", dep_id, uid))
    con.commit()
    con.close()

    st["step"] = "dep_send_receipt"

    bot.send_message(c.message.chat.id, "📩 So‘rovingiz adminga yuborildi.\nEndi chek (skrin) ni shu yerga yuboring.")
    bot.answer_callback_query(c.id)

@bot.message_handler(
    func=lambda m: state.get(m.from_user.id, {}).get("step") == "dep_send_receipt",
    content_types=["photo", "document"]
)
def dep_receipt(m):
    uid = m.from_user.id
    st = state.get(uid)
    dep_id = st["data"]["dep_id"]

    file_id = None
    if m.content_type == "photo":
        file_id = m.photo[-1].file_id
    else:
        file_id = m.document.file_id

    con = db()
    cur = con.cursor()
    cur.execute("UPDATE deposits SET receipt_file_id=? WHERE id=? AND user_id=?", (file_id, dep_id, uid))
    cur.execute("SELECT amount, method FROM deposits WHERE id=?", (dep_id,))
    amount, method = cur.fetchone()
    con.commit()
    con.close()

    # admin approve/reject
    ikb = types.InlineKeyboardMarkup()
    ikb.add(
        types.InlineKeyboardButton("✅ Tasdiq", callback_data=f"depok:{dep_id}"),
        types.InlineKeyboardButton("❌ Rad", callback_data=f"depno:{dep_id}")
    )

    caption = (
        f"💳 Depozit #{dep_id}\n"
        f"User: @{m.from_user.username} ({uid})\n"
        f"Summa: {amount} so‘m\n"
        f"Usul: {method}"
    )

    if m.content_type == "photo":
        bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=ikb)
    else:
        bot.send_document(ADMIN_ID, file_id, caption=caption, reply_markup=ikb)

    bot.send_message(m.chat.id, "✅ Chek yuborildi. Admin tekshiradi.", reply_markup=main_menu(uid))
    state.pop(uid, None)

@bot.callback_query_handler(func=lambda c: c.data.startswith(("depok:", "depno:")))
def dep_admin_decision(c):
    if not is_admin(c.from_user.id):
        return

    action, dep_id = c.data.split(":")
    dep_id = int(dep_id)
    approve = (action == "depok")

    con = db()
    cur = con.cursor()
    cur.execute("SELECT user_id, amount, status FROM deposits WHERE id=?", (dep_id,))
    r = cur.fetchone()
    if not r:
        con.close()
        bot.answer_callback_query(c.id, "Topilmadi.")
        return

    user_id, amount, status = r
    amount = int(amount)

    if status not in ("submitted", "waiting_receipt"):
        con.close()
        bot.answer_callback_query(c.id, "Allaqachon yakunlangan.")
        return

    if approve:
        cur.execute("UPDATE deposits SET status=? WHERE id=?", ("approved", dep_id))
        cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))

        # referal bonus
        ref_uid = get_referred_by(user_id)
        if ref_uid:
            bonus = (amount * REF_BONUS_PERCENT) // 100
            if bonus > 0:
                cur.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (bonus, ref_uid))
                bot.send_message(ref_uid, f"🎁 Referal bonus: +{bonus} so‘m\nDo‘stingiz depozit qildi: {amount} so‘m")

        con.commit()
        con.close()

        bot.send_message(user_id, f"✅ Depozit tasdiqlandi! +{amount} so‘m\n💰 Balans: {get_balance(user_id)} so‘m")
        bot.answer_callback_query(c.id, "Tasdiqlandi!")
    else:
        cur.execute("UPDATE deposits SET status=? WHERE id=?", ("rejected", dep_id))
        con.commit()
        con.close()
        bot.send_message(user_id, "❌ Depozit rad etildi.\nAgar xato bo‘lsa admin bilan bog‘laning.")
        bot.answer_callback_query(c.id, "Rad etildi!")

    bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)

# =======================
# ADMIN PANEL
# =======================
@bot.message_handler(func=lambda m: m.text == "🛠 Admin panel")
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, "🛠 Admin panel:", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga")
def back(m):
    bot.send_message(m.chat.id, "Asosiy menyu:", reply_markup=main_menu(m.from_user.id))

# Admin: Skin qo'shish (section -> weapon -> title -> price -> wear -> used -> photo -> desc)
@bot.message_handler(func=lambda m: m.text == "➕ Skin qo‘shish")
def admin_add_skin(m):
    if not is_admin(m.from_user.id):
        return
    state[m.from_user.id] = {"step": "add_section", "data": {}}
    bot.send_message(m.chat.id, "📂 Bo‘lim tanlang:", reply_markup=sections_kb("addsec"))

@bot.callback_query_handler(func=lambda c: c.data.startswith("addsec:"))
def admin_add_section_pick(c):
    if not is_admin(c.from_user.id):
        return
    section = c.data.split(":", 1)[1]
    st = state.get(c.from_user.id)
    if not st or st.get("step") != "add_section":
        bot.answer_callback_query(c.id, "Sessiya yo‘q.")
        return
    st["data"]["section"] = section
    st["step"] = "add_weapon"
    bot.edit_message_text(
        f"{section}\n\n🔫 Qurol tanlang:",
        c.message.chat.id,
        c.message.message_id,
        reply_markup=weapons_kb("addwep", section)
    )
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("addwep:"))
def admin_add_weapon_pick(c):
    if not is_admin(c.from_user.id):
        return
    weapon = c.data.split(":", 1)[1]
    st = state.get(c.from_user.id)
    if not st or st.get("step") != "add_weapon":
        bot.answer_callback_query(c.id, "Sessiya yo‘q.")
        return
    st["data"]["weapon"] = weapon
    st["step"] = "add_title"
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, f"✅ Qurol: {weapon}\nSkin nomini yozing:")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and state.get(m.from_user.id, {}).get("step") == "add_title")
def admin_add_title(m):
    st = state[m.from_user.id]
    st["data"]["title"] = (m.text or "").strip()
    st["step"] = "add_price"
    bot.send_message(m.chat.id, "Narx (son, so‘m):")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and state.get(m.from_user.id, {}).get("step") == "add_price")
def admin_add_price(m):
    if not (m.text or "").strip().isdigit():
        bot.send_message(m.chat.id, "❗ Faqat son kiriting.")
        return
    st = state[m.from_user.id]
    st["data"]["price"] = int(m.text.strip())
    st["step"] = "add_wear"
    bot.send_message(m.chat.id, "Holatini tanlang:", reply_markup=wear_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("wear:"))
def admin_add_wear_pick(c):
    st = state.get(c.from_user.id)
    if not st or st.get("step") != "add_wear":
        return
    if not is_admin(c.from_user.id):
        return
    wear = c.data.split(":", 1)[1]
    st["data"]["wear"] = wear
    st["step"] = "add_used"
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "Ishlatilgani (masalan: 2 oy) yoki 'skip':")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and state.get(m.from_user.id, {}).get("step") == "add_used")
def admin_add_used(m):
    st = state[m.from_user.id]
    txt = (m.text or "").strip()
    st["data"]["used_note"] = None if txt.lower() == "skip" else txt
    st["step"] = "add_photo"
    bot.send_message(m.chat.id, "Rasm URL (yoki 'skip'):")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and state.get(m.from_user.id, {}).get("step") == "add_photo")
def admin_add_photo(m):
    st = state[m.from_user.id]
    txt = (m.text or "").strip()
    st["data"]["photo_url"] = None if txt.lower() == "skip" else txt
    st["step"] = "add_desc"
    bot.send_message(m.chat.id, "Tavsif (yoki 'skip'):")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and state.get(m.from_user.id, {}).get("step") == "add_desc")
def admin_add_desc(m):
    st = state[m.from_user.id]
    txt = (m.text or "").strip()
    st["data"]["description"] = None if txt.lower() == "skip" else txt

    d = st["data"]
    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO products(section, weapon, title, price, wear, used_note, photo_url, description, active, created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (
        d["section"], d["weapon"], d["title"], d["price"], d["wear"],
        d.get("used_note"), d.get("photo_url"), d.get("description"),
        1, int(time.time())
    ))
    con.commit()
    con.close()

    state.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "✅ Skin katalogga qo‘shildi!", reply_markup=admin_menu())

# Admin: Depozitlar va Buyurtmalar (faqat /orders /deposits ko'rinishida minimal)
@bot.message_handler(func=lambda m: m.text in ("📦 Buyurtmalar", "💳 Depozitlar", "📦 Mahsulotlar"))
def admin_simple_info(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id,
                     "✅ Admin ishlari inline tugmalar bilan keladi:\n"
                     "- Buyurtma kelganda: ✅ Tasdiq / ❌ Rad / 📤 Delivered\n"
                     "- Depozit kelganda: ✅ Tasdiq / ❌ Rad\n\n"
                     "Mahsulotlarni ko‘rish/ochirishni xohlasang keyingi update qo‘shamiz.",
                     reply_markup=admin_menu())

# =======================
# RUN
# =======================
bot.infinity_polling()
