import requests
import time
import sqlite3
import random
import os
import datetime
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "Бот працює!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

# --- КОНФІГУРАЦІЯ ---
TOKEN = '8738009781:AAGsaGihufi6das9Xk89eUl3rwF-J6GS-xc'
URL = f'https://api.telegram.org/bot{TOKEN}/'
DB_NAME = 'forest_novaky_final.db'
PHOTO_PATH = 'my_shkets/' 
TOTAL_PHOTOS = 20

QUEST_TEMPLATES = {
    1: {"desc": "🥩 Вполювати {} кг м'яса для Клану", "energy": 25, "exp": 25},
    2: {"desc": "🦔 Допомога старійшинам Клану", "energy": 50, "exp": 30},
    3: {"desc": "🌿 Назбирати {} кг моху для підстилок", "energy": 25, "exp": 25},
    4: {"desc": "🐾 Відправитись у патрулювання кордонів", "energy": 50, "exp": 40}
}

# --- БАЗА ДАНИХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS novaky 
                      (user_id INTEGER PRIMARY KEY, name TEXT, meat INTEGER DEFAULT 0, 
                       exp INTEGER DEFAULT 0, energy INTEGER DEFAULT 100, last_rest INTEGER, 
                       is_sleeping INTEGER DEFAULT 0, photo_id INTEGER,
                       last_quest_time INTEGER DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS relationships 
                      (user_one INTEGER, user_two INTEGER, points INTEGER, status TEXT,
                       PRIMARY KEY (user_one, user_two))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS user_quests 
                      (user_id INTEGER PRIMARY KEY, date TEXT,
                       q1_id INTEGER, q1_val INTEGER, q1_done INTEGER,
                       q2_id INTEGER, q2_val INTEGER, q2_done INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS rel_cooldowns 
                      (u1 INTEGER, u2 INTEGER, last_interact INTEGER,
                       PRIMARY KEY (u1, u2))''')
    conn.commit(); conn.close()

def get_today_str(): return datetime.datetime.now().strftime("%Y-%m-%d")

def generate_daily_quests(user_id):
    today = get_today_str()
    ids = random.sample([1, 2, 3, 4], 2)
    val1 = random.randint(1, 4) if ids[0] in [1, 3] else 0
    val2 = random.randint(1, 4) if ids[1] in [1, 3] else 0
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT OR REPLACE INTO user_quests VALUES (?, ?, ?, ?, 0, ?, ?, 0)", 
                 (user_id, today, ids[0], val1, ids[1], val2))
    conn.commit(); conn.close()

def update_relation(u1, u2, p_add, status=None):
    p1, p2 = min(u1, u2), max(u1, u2)
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT points FROM relationships WHERE user_one=? AND user_two=?", (p1, p2))
    row = cursor.fetchone()
    pts = max(-100, min(100, (row[0] if row else 0) + p_add))
    st = status if status else ("Друзі" if pts >= 50 else ("Вороги" if pts <= -30 else "Знайомі"))
    conn.execute("INSERT OR REPLACE INTO relationships VALUES (?,?,?,?)", (p1, p2, pts, st))
    conn.execute("INSERT OR REPLACE INTO rel_cooldowns VALUES (?,?,?)", (p1, p2, int(time.time())))
    conn.commit(); conn.close()
    return pts

def get_novak(uid):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_quest_time FROM novaky WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if not row: return None
    now = int(time.time()); name, meat, exp, energy, l_rest, slp, ph, l_qt = row
    rec = (now - l_rest) // (100 if slp else 300)
    if rec > 0:
        energy = min(100, energy + rec)
        conn.execute("UPDATE novaky SET energy=?, last_rest=? WHERE user_id=?", (energy, now, uid)); conn.commit()
    conn.close()
    return {"name": name, "meat": meat, "exp": exp, "energy": energy, "is_sleeping": slp, "photo_id": ph, "last_quest_time": l_qt}

def send_msg(cid, txt): requests.post(URL + 'sendMessage', data={'chat_id': cid, 'text': txt, 'parse_mode': 'Markdown'})

# --- ОСНОВНИЙ ЦИКЛ ---
def main():
    init_db(); keep_alive(); last_id = 0
    while True:
        try:
            res = requests.get(URL + 'getUpdates', params={'offset': last_id, 'timeout': 10}).json()
            for up in res.get("result", []):
                last_id = up["update_id"] + 1
                if "message" not in up or "text" not in up["message"]: continue
                m = up["message"]; txt = m["text"].lower().strip(); cid = m["chat"]["id"]; uid = m["from"]["id"]
                n = get_novak(uid)

                if txt == "/start":
                    if not n:
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO novaky (user_id, name, last_rest, photo_id) VALUES (?,?,?,?)", 
                                   (uid, "Новак", int(time.time()), random.randint(1, TOTAL_PHOTOS)))
                        conn.commit(); conn.close(); generate_daily_quests(uid)
                        send_msg(cid, "🌲 Тебе прийнято в Клан! Напиши 'мій новак'.")
                    else: send_msg(cid, "🐾 Ти вже в Клані!")

                elif n:
                    if "мій новак" in txt:
                        st = "💤 Спить" if n["is_sleeping"] else "🌲 Гуляє"
                        cap = f"🐈 **Новак:** {n['name']}\n🔋 **Енергія:** {n['energy']}/100 ({st})\n🥩 **М'ясо:** {n['meat']} кг\n📈 **Досвід:** {n['exp']}"
                        photo = f"{PHOTO_PATH}{n['photo_id']}.jpg"
                        if os.path.exists(photo):
                            with open(photo, 'rb') as f: requests.post(URL + "sendPhoto", data={'chat_id': cid, 'caption': cap, 'parse_mode': 'Markdown'}, files={'photo': f})
                        else: send_msg(cid, cap)

                    elif txt.startswith("назви "):
                        nn = m["text"][6:].strip()
                        if nn:
                            conn = sqlite3.connect(DB_NAME); conn.execute("UPDATE novaky SET name=? WHERE user_id=?", (nn, uid)); conn.commit(); conn.close()
                            send_msg(cid, f"✨ Тепер тебе звуть {nn}")

                    elif txt == "видалити новака":
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("DELETE FROM novaky WHERE user_id=?", (uid,))
                        conn.execute("DELETE FROM user_quests WHERE user_id=?", (uid,))
                        conn.commit(); conn.close()
                        send_msg(cid, "🗑 Твого новака видалено. Ти можеш почати заново через /start.")

                    elif txt in ["подружитися", "покусати"]:
                        if "reply_to_message" not in m: send_msg(cid, "⚠️ Відповідай на повідомлення іншого кота!"); continue
                        tid = m["reply_to_message"]["from"]["id"]; tn = get_novak(tid)
                        if not tn or tid == uid: continue
                        p1, p2 = min(uid, tid), max(uid, tid)
                        conn = sqlite3.connect(DB_NAME)
                        co_row = conn.execute("SELECT last_interact FROM rel_cooldowns WHERE u1=? AND u2=?", (p1, p2)).fetchone()
                        now = int(time.time())
                        if co_row and (now - co_row[0] < 3600):
                            rem = (3600 - (now - co_row[0])) // 60
                            send_msg(cid, f"⏳ Новак зайнятий, спробуй пізніше. Залишилося: {rem} хв"); conn.close(); continue
                        
                        if txt == "подружитися":
                            p = update_relation(uid, tid, 15)
                            send_msg(cid, f"🤝 {n['name']} та {tn['name']} стали ближче! (+15, разом: {p})")
                        elif txt == "покусати":
                            p = update_relation(uid, tid, -20)
                            send_msg(cid, f"😾 {n['name']} покусав {tn['name']}! (-20, разом: {p})")
                        conn.close()

                    elif txt == "пара":
                        if "reply_to_message" not in m: send_msg(cid, "⚠️ Відповідай на повідомлення того, з ким хочеш бути парою!"); continue
                        tid = m["reply_to_message"]["from"]["id"]
                        if tid == uid: send_msg(cid, "❌ Не можна стати парою самому собі!"); continue
                        p1, p2 = min(uid, tid), max(uid, tid)
                        conn = sqlite3.connect(DB_NAME)
                        row = conn.execute("SELECT points FROM relationships WHERE user_one=? AND user_two=?", (p1, p2)).fetchone()
                        if row and row[0] >= 60:
                            update_relation(uid, tid, 10, "Пара")
                            send_msg(cid, "❤️ Вітаємо! Ви тепер офіційно пара!")
                        else:
                            pts = row[0] if row else 0
                            send_msg(cid, f"❌ Для створення пари потрібно 60 прихильності (у вас {pts}).")
                        conn.close()

                    elif txt == "стосунки":
                        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
                        rels = cursor.execute("SELECT user_one, user_two, points, status FROM relationships WHERE user_one=? OR user_two=?", (uid, uid)).fetchall()
                        if not rels: send_msg(cid, "🍃 Поки що ти одинак."); continue
                        res_txt = "📜 **Твої стосунки:**\n"
                        for r in rels:
                            oid = r[1] if r[0] == uid else r[0]
                            oname = cursor.execute("SELECT name FROM novaky WHERE user_id=?", (oid,)).fetchone()
                            res_txt += f"• {oname[0] if oname else 'Кіт'}: {r[2]}б. ({r[3]})\n"
                        conn.close(); send_msg(cid, res_txt)

                    elif txt == "завдання":
                        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
                        cursor.execute("SELECT date, q1_id, q1_val, q1_done, q2_id, q2_val, q2_done FROM user_quests WHERE user_id=?", (uid,))
                        row = cursor.fetchone(); conn.close()
                        if not row or row[0] != get_today_str(): generate_daily_quests(uid); send_msg(cid, "📜 Оновлюю квести..."); continue
                        def fmt(qid, val, done):
                            inf = QUEST_TEMPLATES[qid]; d = inf['desc'].format(val) if val > 0 else inf['desc']
                            return f"{d} {'✅' if done else '❌'} (⚡-{inf['energy']})"
                        send_msg(cid, f"📜 **Квести:**\n1. {fmt(row[1], row[2], row[3])}\n2. {fmt(row[4], row[5], row[6])}")

                    elif txt in ["завдання 1", "завдання 2"]:
                        if n["is_sleeping"]: send_msg(cid, "💤 Новак спить!"); continue
                        now = int(time.time())
                        if now - n["last_quest_time"] < 3600:
                            rem = (3600-(now-n['last_quest_time']))//60
                            send_msg(cid, f"⏳ Новак зайнятий, спробуй пізніше. Залишилося: {rem} хв"); continue
                        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
                        cursor.execute("SELECT q1_id, q1_done, q2_id, q2_done FROM user_quests WHERE user_id=?", (uid,))
                        q_data = cursor.fetchone()
                        idx, col = (0, "q1_done") if "1" in txt else (2, "q2_done")
                        if q_data[idx+1]: send_msg(cid, "✅ Вже виконано!"); conn.close(); continue
                        inf = QUEST_TEMPLATES[q_data[idx]]
                        if n['energy'] < inf['energy']: send_msg(cid, f"🪫 Мало енергії (треба {inf['energy']}⚡)"); conn.close(); continue
                        conn.execute(f"UPDATE user_quests SET {col}=1 WHERE user_id=?"); conn.execute("UPDATE novaky SET energy=energy-?, exp=exp+?, last_quest_time=? WHERE user_id=?", (inf['energy'], inf['exp'], now, uid)); conn.commit(); conn.close()
                        send_msg(cid, f"🌟 Виконано! +{inf['exp']} досвіду.")

                    elif "полювати" in txt:
                        if n['is_sleeping'] or n['energy'] < 25: send_msg(cid, "💤 Спиш або 🪫 мало сил."); continue
                        m_g, e_g = random.randint(1, 3), random.randint(10, 20)
                        conn = sqlite3.connect(DB_NAME); conn.execute("UPDATE novaky SET meat=meat+?, energy=energy-25, exp=exp+? WHERE user_id=?", (m_g, e_g, uid)); conn.commit(); conn.close()
                        send_msg(cid, f"🏹 Впольовано {m_g} кг м'яса! +{e_g} досвіду.")

                    elif "їсти" in txt:
                        if n['meat'] > 0:
                            conn = sqlite3.connect(DB_NAME); conn.execute("UPDATE novaky SET meat=meat-1, energy=min(100, energy+20) WHERE user_id=?", (uid,)); conn.commit(); conn.close()
                            send_msg(cid, "🍴 +20 ⚡ енергії.")
                        else: send_msg(cid, "🥩 Немає м'яса!")

                    elif "спати" in txt:
                        conn = sqlite3.connect(DB_NAME); conn.execute("UPDATE novaky SET is_sleeping=1, last_rest=? WHERE user_id=?", (int(time.time()), uid)); conn.commit(); conn.close()
                        send_msg(cid, "💤 Заснув.")

                    elif "прокинутись" in txt:
                        conn = sqlite3.connect(DB_NAME); conn.execute("UPDATE novaky SET is_sleeping=0 WHERE user_id=?", (uid,)); conn.commit(); conn.close()
                        send_msg(cid, "☀️ Прокинувся!")

        except Exception as e: print(f"⚠️ Помилка: {e}"); time.sleep(2)

if __name__ == '__main__': main()
                            
