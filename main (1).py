import sqlite3, asyncio, logging, os, html
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton as B, InlineKeyboardMarkup as M,
    KeyboardButton as KB, ReplyKeyboardMarkup as RKM, ReactionTypeEmoji
)
from telegram.constants import ChatType
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ChatMemberHandler, ChatJoinRequestHandler, MessageHandler,
    ContextTypes, filters
)

# ================= CONFIGURATION (PRE-FILLED DATA) =================
BOT_TOKEN = "8372559718:AAHDqOtqBUJDZrPBcuNsl5cIMmEOE9tDHVA"
OWNER_IDS = [8590181678]                  # main owner(s)
BOT_NAME = "Leave Guard Pro"              # home screen pe bot ka naam
UPDATES_LINK = "https://t.me/+Vt-EOhzBv8g4YWNl"   # Updates link
START_VIDEO = ""   # optional video/photo file_id
REACTION = "🔥"
# ===================================================================

logging.basicConfig(level=logging.INFO)
con = sqlite3.connect("bot.db", check_same_thread=False)
con.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS channels(id INTEGER PRIMARY KEY, title TEXT, owner INTEGER);
CREATE TABLE IF NOT EXISTS bans(rid INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER,
  user_id INTEGER, name TEXT, username TEXT, ts TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS white(user_id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
""")

# ---------- DEFAULT VALUES ----------
DEFAULT_DM_TEXT = """🎬 <b>MAIN ID SAFE</b>

🎮 <b>MODS :</b> Fʀᴇᴇ Fɪʀᴇ • BGMI • CODM
🛡️ <b>BENEFIT :</b> Sᴀꜰᴇ & Sᴇᴄᴜʀᴇ
📺 <b>QUALITY :</b> 480ᴘ • 720ᴘ • 1080ᴘ • 4K
⏰ <b>TIME :</b> 1-12 HOURS

✨ <b>GET YOURS NOW!</b>"""

DEFAULT_BTN1_TEXT = "🔑 Get Key & Injector (Main)"
DEFAULT_BTN1_URL = "https://t.me/+qij23lq_uXk0N2U1"
DEFAULT_BTN2_TEXT = "✅ Free Mod Menu"
DEFAULT_BTN2_URL = "https://t.me/+eoRD6Nhfl7I2MmE1"

# Initialize KV defaults
if not con.execute("SELECT 1 FROM kv WHERE k='dm_text'").fetchone():
    con.execute("INSERT INTO kv VALUES('dm_text', ?)", (DEFAULT_DM_TEXT,))
if not con.execute("SELECT 1 FROM kv WHERE k='btn1_url'").fetchone():
    con.execute("INSERT INTO kv VALUES('btn1_url', ?)", (DEFAULT_BTN1_URL,))
if not con.execute("SELECT 1 FROM kv WHERE k='btn2_url'").fetchone():
    con.execute("INSERT INTO kv VALUES('btn2_url', ?)", (DEFAULT_BTN2_URL,))
con.commit()

# ---------- FONT UTILITY ----------
_S = dict(zip("abcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"))
def f(s): return "".join(_S.get(c.lower(), c) for c in s)

LINE = "━━━━━━━━━━━━━━━━━━━━"
def card(title, *lines):
    return f"💎 {f(title)}\n{LINE}\n" + "\n".join(lines) + f"\n{LINE}"

def q(sql, *a):
    cur = con.execute(sql, a); con.commit(); return cur.fetchall()

def btn(text, data=None, url=None, style=None):
    return B(text, callback_data=data, url=url, api_kwargs={"style": style} if style else None)

def kbtn(text, style):
    return KB(f(text), api_kwargs={"style": style})

def is_owner(uid): return uid in OWNER_IDS
def is_admin(uid): return uid in OWNER_IDS or bool(q("SELECT 1 FROM admins WHERE user_id=?", uid))

def can_manage(uid, chat_id):
    r = q("SELECT owner FROM channels WHERE id=?", chat_id)
    return is_admin(uid) or (r and r[0][0] == uid)

# ---------- ADMIN CONTROL PANEL KEYBOARD (COLORFUL STYLES) ----------
LBL = {k: f(k) for k in ["Ban List", "Stats", "Approve User", "Remove Approved",
                         "Unban All", "Start Video", "Broadcast", "Admins", "DM Settings"]}

def panel_kb():
    return RKM([
        [kbtn("Ban List", "primary"), kbtn("Stats", "primary")],
        [kbtn("Approve User", "success"), kbtn("Remove Approved", "success")],
        [kbtn("Unban All", "success"), kbtn("DM Settings", "primary")],
        [kbtn("Start Video", "success"), kbtn("Admins", "danger")],
        [kbtn("Broadcast", "danger")],
    ], resize_keyboard=True, input_field_placeholder=f("Control Panel"))

def custom_dm_kb():
    b1_url = (q("SELECT v FROM kv WHERE k='btn1_url'") or [[DEFAULT_BTN1_URL]])[0][0]
    b2_url = (q("SELECT v FROM kv WHERE k='btn2_url'") or [[DEFAULT_BTN2_URL]])[0][0]
    return M([
        [btn("🔑 Get Key & Injector (Main)", url=b1_url, style="success")],
        [btn("✅ Free Mod Menu", url=b2_url, style="primary")]
    ])

def home_kb():
    return M([
        [btn("➕ Add Me", "addme", style="success")],
        [btn("📢 Updates", url=UPDATES_LINK, style="primary")],
        [btn("📊 Usage & Dashboard", "dash", style="primary")],
    ])

def add_kb(bot_username):
    return M([
        [btn("📢 Add To Channel", url=f"https://t.me/{bot_username}?startchannel&admin=post_messages+delete_messages+restrict_members+invite_users", style="success"),
         btn("👥 Add To Group", url=f"https://t.me/{bot_username}?startgroup&admin=delete_messages+restrict_members+invite_users", style="success")],
        [btn("⬅️ Back", "homekb", style="danger")],
    ])

def tree(title, *lines):
    t = "  ".join(" ".join(w) for w in title.upper().split())
    out = [f"┌──[ 💎 {html.escape(t)} ]", "│"]
    last = max(i for i, l in enumerate(lines) if l)
    for i, l in enumerate(lines):
        out.append("│" if not l else ("└──⇛ " if i == last else "├──⇛ ") + html.escape(l))
    return "<blockquote>" + "\n".join(out) + "</blockquote>"

async def send_media(msg, text, kb):
    vid = (q("SELECT v FROM kv WHERE k='video'") or [[START_VIDEO]])[0][0]
    if vid:
        try:
            src = open(vid, "rb") if os.path.exists(vid) else vid
            sent = await msg.reply_video(src, caption=text, parse_mode="HTML", has_spoiler=True,
                                         reply_markup=kb, supports_streaming=True)
            if src is not vid: q("INSERT OR REPLACE INTO kv VALUES('video',?)", sent.video.file_id)
            return sent
        except Exception as e:
            logging.warning("video send failed: %s", e)
    return await msg.reply_text(text, parse_mode="HTML", reply_markup=kb)

# ---------- WORKING DM FUNCTION (TEXT / PHOTO / VIDEO) ----------
async def send_custom_dm(bot, user_id):
    """Join Request & Leave Ban par direct bhejane wala custom DM"""
    dm_text = (q("SELECT v FROM kv WHERE k='dm_text'") or [[DEFAULT_DM_TEXT]])[0][0]
    dm_media = (q("SELECT v FROM kv WHERE k='dm_media'") or [[None]])[0][0]
    media_type = (q("SELECT v FROM kv WHERE k='dm_media_type'") or [[None]])[0][0]
    kb = custom_dm_kb()
    
    try:
        if dm_media and media_type == "photo":
            await bot.send_photo(user_id, photo=dm_media, caption=dm_text, parse_mode="HTML", reply_markup=kb)
        elif dm_media and media_type == "video":
            await bot.send_video(user_id, video=dm_media, caption=dm_text, parse_mode="HTML", reply_markup=kb)
        else:
            await bot.send_message(user_id, text=dm_text, parse_mode="HTML", reply_markup=kb)
        logging.info(f"Custom DM successfully sent to {user_id}")
    except Exception as e:
        logging.error(f"Failed to send DM to {user_id}: {e}")

async def react(ctx, msg):
    if not REACTION or not msg: return
    try: await ctx.bot.set_message_reaction(msg.chat_id, msg.message_id, [ReactionTypeEmoji(REACTION)])
    except Exception: pass

async def send_home(msg, ctx):
    text = tree(BOT_NAME,
        f("🔒 Auto ban on leave — no re-farming"),
        f("📩 Direct Join-request auto DM"),
        f("♻️ One tap unban / unban all"),
        "",
        f("⚙️ How to activate"),
        f("1️⃣ Add Me dabao"),
        f("2️⃣ Bot ko admin banao"),
        f("3️⃣ /unban100 se last 100 bans reverse"),
        "",
        f("✅ Protection 24/7 automatic"))
    sent = await send_media(msg, text, home_kb())
    await react(ctx, sent)
    return sent

# ---------- COMMANDS ----------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    q("INSERT OR IGNORE INTO users VALUES(?)", u.id)
    await react(ctx, update.message)
    await send_home(update.message, ctx)
    if is_admin(u.id):
        await update.message.reply_text(card("Control Panel", f("👑 Welcome Admin"), f("Neeche keyboard se option chuniye 👇")),
                                        reply_markup=panel_kb())

async def panel_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        await update.message.reply_text(f("👑 Control Panel"), reply_markup=panel_kb())

# ---------- INLINE CALLBACKS ----------
async def on_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    c = update.callback_query; uid = c.from_user.id; d = c.data

    if d == "addme":
        await c.answer(); await c.message.edit_reply_markup(add_kb(ctx.bot.username)); return

    if d == "homekb":
        await c.answer(); await c.message.edit_reply_markup(home_kb()); return

    if d == "home":
        await c.answer(); await c.message.delete(); await send_home(c.message, ctx); return

    if d == "dash":
        await c.answer()
        chs = q("SELECT id,title FROM channels") if is_admin(uid) else q("SELECT id,title FROM channels WHERE owner=?", uid)
        if chs:
            placeholders = ",".join("?" for _ in chs)
            cids = [x[0] for x in chs]
            nb = q(f"SELECT COUNT(*) FROM bans WHERE active=1 AND chat_id IN ({placeholders})", *cids)[0][0]
        else:
            nb = 0
        nw = q("SELECT COUNT(*) FROM white")[0][0]
        text = card("Your Dashboard",
            f("🛡 Protected Channels:"), *(["   • " + t for _, t in chs] or ["   " + f("None")]),
            f("❌ Leave-Bans: ") + str(nb),
            f("⭐ Whitelisted: ") + str(nw),
            "", f("✅ Leave Guard & Auto-DM active"))
        rows = [[btn("Approve User", "appr", style="success"), btn("Remove Approved", "rmappr", style="danger")]]
        for cid, t in chs:
            rows.append([btn(f"🚫 Ban List: {t[:22]}", f"bl:{cid}", style="primary")])
        rows.append([btn("Back to Home", "home", style="primary")])
        if c.message.photo or c.message.video: await c.message.edit_caption(caption=text, reply_markup=M(rows))
        else: await c.message.edit_text(text, reply_markup=M(rows))
        return

    if d in ("appr", "rmappr", "bc", "addadm", "rmadm", "setphoto", "set_dm_media", "set_dm_text", "set_link1", "set_link2"):
        need_owner = d in ("addadm", "rmadm")
        if (need_owner and not is_owner(uid)) or not is_admin(uid):
            await c.answer("Not allowed", show_alert=True); return
        await ask(c.message, ctx, d); await c.answer(); return

    if d.startswith("bl:"):
        cid = int(d[3:])
        if not can_manage(uid, cid): await c.answer("Not allowed", show_alert=True); return
        await c.answer(); await show_ban_list(c.message, cid); return

    if d.startswith("ub:"):
        _, cid, tid = d.split(":"); cid, tid = int(cid), int(tid)
        if not can_manage(uid, cid): await c.answer("Not allowed", show_alert=True); return
        try: await ctx.bot.unban_chat_member(cid, tid, only_if_banned=True)
        except Exception as e: await c.answer(str(e)[:150], show_alert=True); return
        q("UPDATE bans SET active=0 WHERE chat_id=? AND user_id=?", cid, tid)
        await c.answer("Unbanned ✓")
        await c.message.edit_reply_markup(M([[btn("Unbanned ✓", "noop", style="success")]])); return

    if d.startswith("uball:"):
        cid = int(d[6:])
        if not can_manage(uid, cid): await c.answer("Not allowed", show_alert=True); return
        await c.answer("Unban ho raha hai...")
        n = await unban_many(ctx, q("SELECT rid,chat_id,user_id FROM bans WHERE chat_id=? AND active=1", cid))
        await c.message.reply_text(f(f"✅ {n} users unban ho gaye.")); return

    if d.startswith("rmadm:"):
        if not is_owner(uid): await c.answer("Owner only", show_alert=True); return
        q("DELETE FROM admins WHERE user_id=?", int(d[6:])); await c.answer("Removed")
        await c.message.edit_reply_markup(M([[btn("Removed ✓", "noop", style="success")]])); return

    await c.answer()

async def show_ban_list(msg, cid):
    rows_db = q("SELECT user_id,name FROM bans WHERE chat_id=? AND active=1 ORDER BY rid DESC LIMIT 10", cid)
    rows = [[btn(f"Unban {n[:20]}", f"ub:{cid}:{u}", style="success")] for u, n in rows_db]
    rows.append([btn("♻️ Remove All (Unban All)", f"uball:{cid}", style="danger")])
    await msg.reply_text(f("🚫 Banned users (last 10): ") + str(len(rows_db)), reply_markup=M(rows))

async def unban_many(ctx, rows):
    n = 0
    for rid, cid, tid in rows:
        try: await ctx.bot.unban_chat_member(cid, tid, only_if_banned=True); n += 1
        except Exception: pass
        q("UPDATE bans SET active=0 WHERE rid=?", rid)
        await asyncio.sleep(0.05)
    return n

async def ask(msg, ctx, mode):
    ctx.user_data["await"] = mode
    p = {
        "appr": "Approve karne ke liye user ID bhejo:",
        "rmappr": "Whitelist se hatane ke liye user ID bhejo:",
        "bc": "📢 Jo message broadcast karna hai wo bhejo (text/photo/video):",
        "addadm": "Naya admin ka user ID bhejo:",
        "rmadm": "",
        "setphoto": "🎬 Start video bhejo (jo /start pe dikhegi):",
        "set_dm_media": "📸 Custom DM ke liye Photo ya Video bhejo:",
        "set_dm_text": "📝 Custom DM ke liye Naya Text Message bhejo (HTML formatting allowed):",
        "set_link1": "🔗 Button 1 (Get Key) ka Link bhejo (e.g. https://t.me/yourchannel):",
        "set_link2": "🔗 Button 2 (Free Mod Menu) ka Link bhejo (e.g. https://t.me/yourchannel):"
    }[mode]
    
    if mode == "rmadm":
        rows = [[btn(f"Remove {i}", f"rmadm:{i}", style="danger")] for (i,) in q("SELECT user_id FROM admins")]
        await msg.reply_text(f("Admins list") if rows else f("Koi extra admin nahi hai."), reply_markup=M(rows) if rows else None)
        ctx.user_data.pop("await", None); return
    await msg.reply_text(f(p))

async def unban100(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rows = [r for r in q("SELECT rid,chat_id,user_id FROM bans WHERE active=1 ORDER BY rid DESC LIMIT 100")
            if can_manage(uid, r[1])]
    n = await unban_many(ctx, rows)
    await update.message.reply_text(f(f"✅ Last {n} auto-bans reverse kar diye."))

# ---------- MESSAGES & PANEL INPUTS ----------
async def on_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = update.message; uid = m.from_user.id
    if not is_admin(uid): return
    t = m.text or ""

    if t in LBL.values():
        ctx.user_data.pop("await", None)
        key = next(k for k, v in LBL.items() if v == t)
        if key == "Ban List":
            chs = q("SELECT id,title FROM channels")
            if not chs: await m.reply_text(f("Koi channel connected nahi hai.")); return
            await m.reply_text(f("Channel chuniye:"), reply_markup=M(
                [[btn(x[1][:30], f"bl:{x[0]}", style="primary")] for x in chs]))
        elif key == "Stats":
            await m.reply_text(card("Bot Stats",
                f("👥 Users: ") + str(q("SELECT COUNT(*) FROM users")[0][0]),
                f("🛡 Channels: ") + str(q("SELECT COUNT(*) FROM channels")[0][0]),
                f("❌ Active Bans: ") + str(q("SELECT COUNT(*) FROM bans WHERE active=1")[0][0]),
                f("⭐ Whitelisted: ") + str(q("SELECT COUNT(*) FROM white")[0][0]),
                f("👮 Admins: ") + str(q("SELECT COUNT(*) FROM admins")[0][0] + len(OWNER_IDS))))
        elif key == "Unban All":
            await m.reply_text(f("⏳ Sab unban ho rahe hain..."))
            n = await unban_many(ctx, q("SELECT rid,chat_id,user_id FROM bans WHERE active=1"))
            await m.reply_text(f(f"✅ {n} users unban ho gaye."))
        elif key == "Approve User": await ask(m, ctx, "appr")
        elif key == "Remove Approved": await ask(m, ctx, "rmappr")
        elif key == "Start Video": await ask(m, ctx, "setphoto")
        elif key == "Broadcast": await ask(m, ctx, "bc")
        elif key == "DM Settings":
            b1 = (q("SELECT v FROM kv WHERE k='btn1_url'") or [[DEFAULT_BTN1_URL]])[0][0]
            b2 = (q("SELECT v FROM kv WHERE k='btn2_url'") or [[DEFAULT_BTN2_URL]])[0][0]
            m_type = (q("SELECT v FROM kv WHERE k='dm_media_type'") or [["None"]])[0][0]
            text = card("DM Settings",
                "⚙️ Customize Join/Leave DM Message & Buttons:", "",
                f(f"🖼️ Current Media Type: {m_type.upper()}"),
                f(f"🔗 Button 1 Link: {b1}"),
                f(f"🔗 Button 2 Link: {b2}")
            )
            rows = [
                [btn("🖼 Set DM Photo/Video", "set_dm_media", style="primary")],
                [btn("📝 Set DM Text Message", "set_dm_text", style="primary")],
                [btn("🔗 Set Button 1 Link", "set_link1", style="success")],
                [btn("🔗 Set Button 2 Link", "set_link2", style="success")]
            ]
            await m.reply_text(text, reply_markup=M(rows))
        elif key == "Admins":
            if not is_owner(uid): await m.reply_text(f("Sirf owner ke liye.")); return
            lst = ", ".join(str(i) for (i,) in q("SELECT user_id FROM admins")) or "-"
            await m.reply_text(f("👮 Admins: ") + lst, reply_markup=M(
                [[btn("Add Admin", "addadm", style="success"), btn("Remove Admin", "rmadm", style="danger")]]))
        return

    mode = ctx.user_data.pop("await", None)
    if mode == "bc":
        users = [r[0] for r in q("SELECT id FROM users")]
        ok = fail = 0
        st = await m.reply_text(f(f"Broadcast shuru: {len(users)} users"))
        for tgt in users:
            try: await ctx.bot.copy_message(tgt, m.chat_id, m.message_id); ok += 1
            except Exception: fail += 1
            await asyncio.sleep(0.05)
        await st.edit_text(f("📢 Broadcast done") + f"\n✅ {ok}\n❌ {fail}")
    elif mode == "setphoto" and (m.video or m.animation):
        fid = (m.video or m.animation).file_id
        q("INSERT OR REPLACE INTO kv VALUES('video',?)", fid)
        await m.reply_text(f("🎬 Start video set ho gayi."))
    elif mode == "set_dm_media":
        if m.photo:
            fid = m.photo[-1].file_id
            q("INSERT OR REPLACE INTO kv VALUES('dm_media',?)", fid)
            q("INSERT OR REPLACE INTO kv VALUES('dm_media_type',?)", "photo")
            await m.reply_text("✅ DM Custom Photo set ho gayi.")
        elif m.video or m.animation:
            fid = (m.video or m.animation).file_id
            q("INSERT OR REPLACE INTO kv VALUES('dm_media',?)", fid)
            q("INSERT OR REPLACE INTO kv VALUES('dm_media_type',?)", "video")
            await m.reply_text("✅ DM Custom Video set ho gayi.")
        else:
            await m.reply_text("❌ Kripya Photo ya Video bhejen.")
    elif mode == "set_dm_text" and m.text:
        q("INSERT OR REPLACE INTO kv VALUES('dm_text',?)", m.text_html)
        await m.reply_text("✅ DM Text Message update ho gaya.")
    elif mode == "set_link1" and m.text and m.text.startswith("http"):
        q("INSERT OR REPLACE INTO kv VALUES('btn1_url',?)", m.text.strip())
        await m.reply_text("✅ Button 1 Link update ho gaya.")
    elif mode == "set_link2" and m.text and m.text.startswith("http"):
        q("INSERT OR REPLACE INTO kv VALUES('btn2_url',?)", m.text.strip())
        await m.reply_text("✅ Button 2 Link update ho gaya.")

# ---------- BOT ADDED/REMOVED ----------
async def my_member(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    m = update.my_chat_member; chat = m.chat
    if chat.type == ChatType.PRIVATE: return
    if m.new_chat_member.status == "administrator":
        q("INSERT OR REPLACE INTO channels VALUES(?,?,?)", chat.id, chat.title, m.from_user.id)
        try:
            await ctx.bot.send_message(m.from_user.id,
                card("Channel Connected", f("🛡 Title: ") + chat.title, f"⚙️ ID: {chat.id}", "",
                     f("✅ Auto-Ban on Leave active"), f("✅ Join-Request Auto-DM active")))
        except Exception: pass
    elif m.new_chat_member.status in ("left", "kicked"):
        q("DELETE FROM channels WHERE id=?", chat.id)

# ---------- LEAVE -> BAN -> SEND DM (WITHOUT AUTO APPROVE) ----------
async def member_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cm = update.chat_member; chat = cm.chat
    old, new = cm.old_chat_member.status, cm.new_chat_member.status
    if new != "left" or old in ("left", "kicked", "administrator", "creator"): return
    user = cm.new_chat_member.user
    if user.is_bot or q("SELECT 1 FROM white WHERE user_id=?", user.id): return
    ch = q("SELECT owner FROM channels WHERE id=?", chat.id)
    if not ch:
        q("INSERT OR REPLACE INTO channels VALUES(?,?,?)", chat.id, chat.title, OWNER_IDS[0])
        ch = [(OWNER_IDS[0],)]
    owner = ch[0][0]
    
    try:
        # 1. Ban User
        await ctx.bot.ban_chat_member(chat.id, user.id)
        # 2. Send Custom DM to banned user
        await send_custom_dm(ctx.bot, user.id)
    except Exception as e:
        logging.warning("ban/dm failed: %s", e)

    ts = datetime.now().strftime("%Y-%m-%d  |  %H:%M:%S")
    q("INSERT INTO bans(chat_id,user_id,name,username,ts) VALUES(?,?,?,?,?)",
      chat.id, user.id, user.full_name, user.username or "", ts)
    
    text = card("User Left & Banned",
        f"🕒 {f('Time')}: {ts}", "",
        f("👤 User Details"),
        f"• {f('Name')}: {user.full_name}",
        f"• {f('Username')}: {'@'+user.username if user.username else 'N/A'}",
        f"• ID: {user.id}", "",
        f("📣 Channel Details"),
        f"• {f('Name')}: {chat.title}",
        f"• ID: {chat.id}", "",
        f("🚫 Automatically Banned & DM Sent"))
    kb = M([[btn("Remove User (Unban)", f"ub:{chat.id}:{user.id}", style="success")]])
    try: await ctx.bot.send_message(owner, text, reply_markup=kb)
    except Exception: pass

# ---------- JOIN REQUEST -> SEND CUSTOM DM ONLY (NO AUTO APPROVE) ----------
async def join_req(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    r = update.chat_join_request
    # Sirf Custom DM Bhejayega, Approve Bilkul Nahi Karega
    await send_custom_dm(ctx.bot, r.from_user.id)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    P = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", start, P))
    app.add_handler(CommandHandler("panel", panel_cmd, P))
    app.add_handler(CommandHandler("unban100", unban100, P))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(ChatMemberHandler(my_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(member_update, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatJoinRequestHandler(join_req))
    app.add_handler(MessageHandler(P & ~filters.COMMAND, on_msg))
    
    logging.info("Bot starting polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
