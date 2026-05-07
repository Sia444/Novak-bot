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

TOKEN = '8738009781:AAGsaGihufi6das9Xk89eUl3rwF-J6GS-xc'
URL = f'https://api.telegram.org/bot{TOKEN}/'
DB_NAME = 'forest_novaky_v4.db'
PHOTO_PATH = 'my_shkets/' 
TOTAL_PHOTOS = 20

QUEST_TEMPLATES = {
    1: {"desc": "🥩 Вполювати {} кг м'яса для Клану", "energy": 25, "exp": 25},
    2: {"desc": "🦔 Допомога старійшинам Клану", "energy": 50, "exp": 30},
    3: {"desc": "🌿 Назбирати {} кг моху для підстилок", "energy": 25, "exp": 25},
    4: {"desc": "🐾 Відправитись у патрулювання кордонів", "energy": 50, "exp": 40}
}

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
    conn.commit(); conn.close()

def get_today_str(): return datetime.datetime.now().strftime("%Y-%m-%d")

def generate_daily_quests(user_id):
    today = get_today_str()
    ids = random.sample([1, 2, 3, 4], 2)
    val1 = random.randint(1, 4) if ids[0] == 1 else (random.randint(1, 3) if ids[0] == 3 else 0)
    val2 = random.randint(1, 4) if ids[1] == 1 else (random.randint(1, 3) if ids[1] == 3 else 0)
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT OR REPLACE INTO user_quests VALUES (?, ?, ?, ?, 0, ?, ?, 0)", 
                 (user_id, today, ids[0], val1, ids[1], val2))
    conn.commit(); conn.close()

def get_user_quests(user_id):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT date, q1_id, q1_val, q1_done, q2_id, q2_val, q2_done FROM user_quests WHERE user_id=?", (user_id,))
    row = cursor.fetchone(); conn.close()
    if not row or row[0] != get_today_str():
        generate_daily_quests(user_id)
        return get_user_quests(user_id)
    return {"q1": {"id": row[1], "val": row[2], "done": row[3]}, "q2": {"id": row[4], "val": row[5], "done": row[6]}}

def update_relation(u1, u2, p_add, status=None):
    p1, p2 = min(u1, u2), max(u1, u2)
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT points, status FROM relationships WHERE user_one=? AND user_two=?", (p1, p2))
    row = cursor.fetchone()
    pts = max(-100, min(100, (row[0] if row else 0) + p_add))
    st = status if status else ("Друзі" if pts >= 50 else ("Вороги" if pts <= -30 else "Знайомі"))
    conn.execute("INSERT OR REPLACE INTO relationships VALUES (?,?,?,?)", (p1, p2, pts, st))
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
                        send_msg(cid, cap)

                    elif txt == "видалити новака":
                        conn = sqlite3.connect(DB_NAME); conn.execute("DELETE FROM novaky WHERE user_id=?", (uid,))
                        conn.execute("DELETE FROM user_quests WHERE user_id=?", (uid,)); conn.commit(); conn.close()
                        send_msg(cid, "💥 Твій новак покинув Клан.")

                    elif txt == "завдання":
                        q = get_user_quests(uid)
                        def get_q_text(qd):
                            info = QUEST_TEMPLATES[qd['id']]
                            desc = info['desc'].format(qd['val']) if qd['val'] > 0 else info['desc']
                            status = "✅" if qd['done'] else "❌"
                            return f"{desc} {status} (⚡-{info['energy']})"
                        send_msg(cid, f"📜 **Квести:**\n1. {get_q_text(q['q1'])}\n2. {get_q_text(q['q2'])}")

                    elif txt in ["завдання 1", "завдання 2"]:
                        if n["is_sleeping"]: send_msg(cid, "💤 Новак спить!"); continue
                        now = int(time.time()); diff = now - n["last_quest_time"]
                        if diff < 3600: send_msg(cid, f"⏳ Зачекай {(3600-diff)//60} хв."); continue
                        
                        qn_key = "q1" if "1" in txt else "q2"; qs = get_user_quests(uid); qd = qs[qn_key]
                        if qd['done']: send_msg(cid, "✅ Вже виконано!"); continue
                        inf = QUEST_TEMPLATES[qd['id']]
                        if n['energy'] < inf['energy']: send_msg(cid, f"🪫 Мало енергії (треба {inf['energy']}⚡)!"); continue

                        conn = sqlite3.connect(DB_NAME)
                        conn.execute(f"UPDATE user_quests SET {qn_key}_done=1 WHERE user_id=?", (uid,))
                        # Енергія витрачається, досвід додається, АЛЕ м'ясо в рюкзак НЕ йде
                        conn.execute("UPDATE novaky SET energy=energy-?, exp=exp+?, last_quest_time=? WHERE user_id=?", 
                                   (inf['energy'], inf['exp'], now, uid))
                        conn.commit(); conn.close()
                        send_msg(cid, f"🌟 Завдання виконано! Ти приніс здобич Клану. -{inf['energy']}⚡, +{inf['exp']} досвіду.")

                    elif txt in ["подружитися", "покусати", "пара"]:
                        if "reply_to_message" not in m: send_msg(cid, "⚠️ Відповідай на повідомлення!"); continue
                        tid = m["reply_to_message"]["from"]["id"]; tn = get_novak(tid)
                        if not tn or tid == uid: continue
                        if txt == "подружитися":
                            p = update_relation(uid, tid, 15)
                            send_msg(cid, f"🤝 {n['name']} та {tn['name']} стали ближче! (+15, разом: {p})")
                        elif txt == "покусати":
                            p = update_relation(uid, tid, -20)
                            send_msg(cid, f"😾 {n['name']} покусав {tn['name']}! (-20, разом: {p})")
                        elif txt == "пара":
                            p1, p2 = min(uid, tid), max(uid, tid)
                            conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
                            cursor.execute("SELECT points FROM relationships WHERE user_one=? AND user_two=?", (p1, p2))
                            row = cursor.fetchone()
                            if row and row[0] >= 60: update_relation(uid, tid, 10, "Пара"); send_msg(cid, "❤️ Ви тепер пара!")
                            else: send_msg(cid, f"❌ Треба 60 прихильності (у вас {row[0] if row else 0}).")

                    elif txt == "стосунки":
                        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
                        rels = cursor.execute("SELECT user_one, user_two, points, status FROM relationships WHERE user_one=? OR user_two=?", (uid, uid)).fetchall()
                        if not rels: send_msg(cid, "🍃 Немає стосунків."); continue
                        res = "📜 **Твої стосунки:**\n"
                        for r in rels:
                            oid = r[1] if r[0] == uid else r[0]
                            oname = cursor.execute("SELECT name FROM novaky WHERE user_id=?", (oid,)).fetchone()
                            res += f"• {oname[0] if oname else 'Кіт'}: {r[2]}б. ({r[3]})\n"
                        conn.close(); send_msg(cid, res)

                    elif "полювати" in txt:
                        if n['energy'] < 25: send_msg(cid, "🪫 Треба 25⚡"); continue
                        m_g, e_g = random.randint(1, 3), random.randint(10, 20)
                        conn = sqlite3.connect(DB_NAME)
                        # Тут м'ясо ДОДАЄТЬСЯ новаку, бо це особисте полювання
                        conn.execute("UPDATE novaky SET meat=meat+?, energy=energy-25, exp=exp+? WHERE user_id=?", (m_g, e_g, uid))
                        conn.commit(); conn.close(); send_msg(cid, f"🏹 Впольовано {m_g} кг м'яса для себе! +{e_g} досвіду.")

                    elif "їсти" in txt:
                        if n['meat'] > 0:
                            conn = sqlite3.connect(DB_NAME); conn.execute("UPDATE novaky SET meat=meat-1, energy=min(100, energy+20) WHERE user_id=?", (uid,))
                            conn.commit(); conn.close(); send_msg(cid, "🍴 +20 ⚡ енергії.")
                        else: send_msg(cid, "🥩 Немає м'яса! Сходи на полювання (команда 'полювати').")

                    elif "спати" in txt:
                        conn = sqlite3.connect(DB_NAME); conn.execute("UPDATE novaky SET is_sleeping=1, last_rest=? WHERE user_id=?", (int(time.time()), uid))
                        conn.commit(); conn.close(); send_msg(cid, "💤 Заснув.")

                    elif "прокинутись" in txt:
                        conn = sqlite3.connect(DB_NAME); conn.execute("UPDATE novaky SET is_sleeping=0 WHERE user_id=?", (uid,))
                        conn.commit(); conn.close(); send_msg(cid, "☀️ Прокинувся!")

        except Exception as e: time.sleep(2)

if __name__ == '__main__': main()
                            
