import requests
import time
import sqlite3
import random
import json
import os
import datetime
from flask import Flask
from threading import Thread

# --- СЕРВЕР ДЛЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Бот працює!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- КОНФІГУРАЦІЯ ---
TOKEN = '8738009781:AAGsaGihufi6das9Xk89eUl3rwF-J6GS-xc'
URL = f'https://api.telegram.org/bot{TOKEN}/'
DB_NAME = 'forest_novaky_v4.db'
PHOTO_PATH = 'my_shkets/' 
TOTAL_PHOTOS = 20

QUEST_TYPES = {
    1: {"type": "meat", "desc": "🥩 Вполювати від 1 до 4 кг м'яса для Клану", "energy": 25},
    2: {"type": "elders", "desc": "🦔 Допомога старійшинам Клану", "energy": 50, "exp": 30},
    3: {"type": "moss", "desc": "🌿 Назбирати від 1 до 3 кг моху для підстилок", "energy": 25},
    4: {"type": "patrol", "desc": "🐾 Відправитись у патрулювання кордонів", "energy": 50, "exp": 40}
}

# --- БАЗА ДАНИХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS novaky 
                      (user_id INTEGER PRIMARY KEY, name TEXT, meat INTEGER, 
                       exp INTEGER, energy INTEGER, last_rest INTEGER, 
                       is_sleeping INTEGER DEFAULT 0, photo_id INTEGER,
                       last_hunt INTEGER DEFAULT 0, last_train INTEGER DEFAULT 0,
                       last_rel INTEGER DEFAULT 0, last_quest_time INTEGER DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS relationships 
                      (user_one INTEGER, user_two INTEGER, points INTEGER, status TEXT,
                       PRIMARY KEY (user_one, user_two))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS user_quests 
                      (user_id INTEGER PRIMARY KEY, date TEXT,
                       q1_id INTEGER, q1_target INTEGER, q1_current INTEGER, q1_done INTEGER,
                       q2_id INTEGER, q2_target INTEGER, q2_current INTEGER, q2_done INTEGER)''')
    conn.commit()
    conn.close()

# --- ЛОГІКА КВЕСТІВ ---
def get_today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def generate_daily_quests(user_id):
    today = get_today_str()
    chosen_ids = random.sample([1, 2, 3, 4], 2)
    q1_id, q2_id = chosen_ids[0], chosen_ids[1]
    q1_target = random.randint(1, 4) if q1_id == 1 else (random.randint(1, 3) if q1_id == 3 else 0)
    q2_target = random.randint(1, 4) if q2_id == 1 else (random.randint(1, 3) if q2_id == 3 else 0)
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''INSERT OR REPLACE INTO user_quests 
                    (user_id, date, q1_id, q1_target, q1_current, q1_done, q2_id, q2_target, q2_current, q2_done) 
                    VALUES (?, ?, ?, ?, 0, 0, ?, ?, 0, 0)''', 
                 (user_id, today, q1_id, q1_target, q2_id, q2_target))
    conn.commit()
    conn.close()

def get_user_quests(user_id):
    today = get_today_str()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT date, q1_id, q1_target, q1_current, q1_done, q2_id, q2_target, q2_current, q2_done FROM user_quests WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or row[0] != today:
        generate_daily_quests(user_id)
        return get_user_quests(user_id)
    return {
        "q1": {"id": row[1], "target": row[2], "current": row[3], "done": row[4]},
        "q2": {"id": row[5], "target": row[6], "current": row[7], "done": row[8]}
    }

# --- СТОСУНКИ ---
def get_relation(u1, u2):
    p1, p2 = min(u1, u2), max(u1, u2)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT points, status FROM relationships WHERE user_one=? AND user_two=?", (p1, p2))
    row = cursor.fetchone()
    conn.close()
    if row: return {"points": row[0], "status": row[1]}
    return {"points": 0, "status": "Знайомі"}

def update_relation(u1, u2, points_add, set_status=None):
    p1, p2 = min(u1, u2), max(u1, u2)
    current = get_relation(p1, p2)
    new_points = max(-100, min(100, current["points"] + points_add))
    status = set_status if set_status else current["status"]
    if not set_status:
        if new_points >= 50: status = "Друзі"
        elif new_points <= -30: status = "Вороги"
        else: status = "Знайомі"
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT OR REPLACE INTO relationships VALUES (?, ?, ?, ?)", (p1, p2, new_points, status))
    conn.commit()
    conn.close()
    return {"points": new_points, "status": status}

# --- ОСНОВНІ ФУНКЦІЇ ---
def get_and_refresh_novak(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_hunt, last_train, last_rel, last_quest_time FROM novaky WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row: 
        conn.close()
        return None
    name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_hunt, last_train, last_rel, last_quest_time = row
    now = int(time.time())
    speed = 100 if is_sleeping else 300
    recovered = (now - last_rest) // speed
    if recovered > 0:
        energy = min(100, energy + recovered)
        conn.execute("UPDATE novaky SET energy = ?, last_rest = ? WHERE user_id = ?", (energy, now, user_id))
        conn.commit()
    conn.close()
    return {"name": name, "meat": meat, "exp": exp, "energy": energy, "is_sleeping": is_sleeping, "photo_id": photo_id, "last_hunt": last_hunt, "last_train": last_train, "last_rel": last_rel, "last_quest_time": last_quest_time}

def send_msg(chat_id, text):
    return requests.post(URL + 'sendMessage', data={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'})

def send_profile(chat_id, n):
    status = "💤 Спить" if n["is_sleeping"] else "🌲 Гуляє"
    caption = f"🐈 **Новак:** {n['name']}\n🔋 **Енергія:** {n['energy']}/100 ({status})\n🥩 **Здобич:** {n['meat']} кг\n📈 **Досвід:** {n['exp']}"
    photo = os.path.join(PHOTO_PATH, f"{n['photo_id']}.jpg")
    if os.path.exists(photo):
        with open(photo, 'rb') as f:
            requests.post(URL + "sendPhoto", data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}, files={'photo': f})
    else: send_msg(chat_id, caption)

# --- ГОЛОВНИЙ ЦИКЛ ---
def main():
    init_db()
    keep_alive()
    last_id = 0
    while True:
        try:
            res = requests.get(URL + 'getUpdates', params={'offset': last_id, 'timeout': 10}).json()
            for update in res.get("result", []):
                last_id = update["update_id"] + 1
                if "message" not in update or "text" not in update["message"]: continue
                
                msg = update["message"]
                text = msg["text"].lower().strip()
                cid = msg["chat"]["id"]
                uid = msg["from"]["id"]
                n = get_and_refresh_novak(uid)

                if text == "/start":
                    if not n:
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO novaky (user_id, name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_quest_time) VALUES (?,?,?,?,?,?,?,?,?)", 
                                   (uid, "Новак", 0, 0, 100, int(time.time()), 0, random.randint(1, TOTAL_PHOTOS), 0))
                        conn.commit(); conn.close()
                        generate_daily_quests(uid)
                        send_msg(cid, "🌲 Новака знайдено! Напиши 'мій новак'.")
                    else: send_msg(cid, "🐾 У тебе вже є новак!")

                elif n:
                    if "мій новак" in text:
                        send_profile(cid, n)

                    elif text == "завдання":
                        q = get_user_quests(uid)
                        def fmt(qd, num):
                            inf = QUEST_TYPES[qd["id"]]
                            if qd["done"]: return f"{num}. {inf['desc']} — ✅"
                            prog = f" ({qd['current']}/{qd['target']}кг)" if qd["target"] > 0 else ""
                            return f"{num}. {inf['desc']}{prog} — ⚡{inf['energy']}"
                        res_text = f"📜 **Квести для {n['name']}:**\n\n{fmt(q['q1'], 1)}\n{fmt(q['q2'], 2)}\n\n`завдання 1` або `завдання 2`"
                        send_msg(cid, res_text)

                    elif text in ["завдання 1", "завдання 2"]:
                        if n["is_sleeping"]: send_msg(cid, "💤 Новак спить!"); continue
                        
                        now = int(time.time())
                        diff = now - n["last_quest_time"]
                        if diff < 3600:
                            rem = (3600 - diff) // 60
                            send_msg(cid, f"⏳ Завдання можна виконувати лише раз на годину! Зачекай ще **{rem} хв**.")
                            continue

                        qn = 1 if "1" in text else 2
                        qs = get_user_quests(uid); qd = qs["q1"] if qn == 1 else qs["q2"]
                        inf = QUEST_TYPES[qd["id"]]
                        if qd["done"]: send_msg(cid, "✅ Вже виконано!"); continue
                        if n["energy"] < inf["energy"]: send_msg(cid, f"🪫 Треба {inf['energy']}⚡!"); continue
                        
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE novaky SET last_quest_time=? WHERE user_id=?", (now, uid))
                        
                        if inf["type"] in ["meat", "moss"]:
                            gain = random.randint(1, 2)
                            new_c = min(qd["target"], qd["current"] + gain)
                            done = 1 if new_c >= qd["target"] else 0
                            sql = "UPDATE user_quests SET q1_current=?, q1_done=? WHERE user_id=?" if qn==1 else "UPDATE user_quests SET q2_current=?, q2_done=? WHERE user_id=?"
                            conn.execute(sql, (new_c, done, uid))
                            conn.execute("UPDATE novaky SET energy=energy-? WHERE user_id=?", (inf["energy"], uid))
                            if done: conn.execute("UPDATE novaky SET exp=exp+25 WHERE user_id=?", (uid,))
                            send_msg(cid, f"🎒 Знайдено! Прогрес: {new_c}/{qd['target']}")
                        else:
                            sql = "UPDATE user_quests SET q1_done=1 WHERE user_id=?" if qn==1 else "UPDATE user_quests SET q2_done=1 WHERE user_id=?"
                            conn.execute(sql, (uid,))
                            conn.execute("UPDATE novaky SET exp=exp+?, energy=energy-? WHERE user_id=?", (inf["exp"], inf["energy"], uid))
                            send_msg(cid, f"✅ Виконано! +{inf['exp']} досвіду.")
                        conn.commit(); conn.close()

                    elif "полювати" in text:
                        if n["energy"] < 25: send_msg(cid, "🪫 Мало енергії (треба 25)."); continue
                        m = random.randint(1, 3); e = random.randint(10, 20)
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE novaky SET meat=meat+?, energy=energy-25, exp=exp+? WHERE user_id=?", (m, e, uid))
                        conn.commit(); conn.close()
                        send_msg(cid, f"🏹 Полювання: +{m}кг м'яса, +{e} ✨ досвіду.")

                    elif "тренувати" in text:
                        if n["energy"] < 30: send_msg(cid, "🪫 Треба 30⚡."); continue
                        e = random.randint(25, 45)
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE novaky SET exp=exp+?, energy=energy-30 WHERE user_id=?", (e, uid))
                        conn.commit(); conn.close()
                        send_msg(cid, f"⚔️ Тренування: +{e} ✨ досвіду!")

                    elif text in ["подружитися", "покусати", "пара"]:
                        if "reply_to_message" not in msg: send_msg(cid, "⚠️ Тільки через Reply!"); continue
                        tid = msg["reply_to_message"]["from"]["id"]
                        if tid == uid: continue
                        tn = get_and_refresh_novak(tid)
                        if not tn: continue
                        
                        if text == "подружитися":
                            r = update_relation(uid, tid, 15)
                            send_msg(cid, f"🤝 {n['name']} та {tn['name']} тепер ближче! ({r['points']} бал.)")
                        elif text == "покусати":
                            r = update_relation(uid, tid, -20)
                            send_msg(cid, f"😾 {n['name']} покусав {tn['name']}! ({r['points']} бал.)")
                        elif text == "пара":
                            cur = get_relation(uid, tid)
                            if cur["points"] < 60: send_msg(cid, "❌ Мало прихильності!"); continue
                            update_relation(uid, tid, 10, "Пара")
                            send_msg(cid, f"❤️ {n['name']} та {tn['name']} тепер пара!")

                    elif text == "стосунки":
                        conn = sqlite3.connect(DB_NAME)
                        rels = conn.execute("SELECT user_one, user_two, points, status FROM relationships WHERE user_one=? OR user_two=?", (uid, uid)).fetchall()
                        if not rels: send_msg(cid, "🍃 Поки нікого немає."); continue
                        res = "📜 **Твої зв'язки:**\n"
                        for r in rels:
                            oid = r[1] if r[0] == uid else r[0]
                            oname = conn.execute("SELECT name FROM novaky WHERE user_id=?", (oid,)).fetchone()
                            res += f"• {oname[0] if oname else 'Кіт'}: {r[2]}б. ({r[3]})\n"
                        conn.close(); send_msg(cid, res)

                    elif text == "топ":
                        conn = sqlite3.connect(DB_NAME)
                        tops = conn.execute("SELECT name, exp FROM novaky ORDER BY exp DESC LIMIT 10").fetchall()
                        conn.close()
                        msg_t = "🏆 **ТОП-10:**\n" + "\n".join([f"{i+1}. {r[0]} - {r[1]}✨" for i, r in enumerate(tops)])
                        send_msg(cid, msg_t)

                    elif text.startswith("назви "):
                        new_n = msg["text"][6:].strip()
                        if new_n:
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("UPDATE novaky SET name=? WHERE user_id=?", (new_name, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"✨ Нове ім'я: {new_n}")

                    elif "спати" in text:
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE novaky SET is_sleeping=1, last_rest=? WHERE user_id=?", (int(time.time()), uid))
                        conn.commit(); conn.close()
                        send_msg(cid, "💤 На добраніч!")

                    elif "прокинутись" in text:
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE novaky SET is_sleeping=0 WHERE user_id=?", (uid,))
                        conn.commit(); conn.close()
                        send_msg(cid, "☀️ Прокинувся!")

                    elif "їсти" in text:
                        if n["meat"] > 0:
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("UPDATE novaky SET meat=meat-1, energy=min(100, energy+20) WHERE user_id=?", (uid,))
                            conn.commit(); conn.close()
                            send_msg(cid, "🍴 Поїв! +20🔋")
                        else: send_msg(cid, "🥩 Немає м'яса!")

        except Exception as e:
            print(f"Error: {e}"); time.sleep(2)

if __name__ == '__main__':
    main()
    
