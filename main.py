import requests, time, sqlite3, random, json, os
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "Бот живе: тренування, топ та стосунки працюють!"

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

TOKEN = '8738009781:AAGsaGihufi6das9Xk89eUl3rwF-J6GS-xc'
URL = f'https://api.telegram.org/bot{TOKEN}/'
PHOTO_PATH = 'my_shkets/' 
TOTAL_PHOTOS = 20

def init_db():
    conn = sqlite3.connect('forest_novaky.db')
    # Основна таблиця котів
    conn.execute('''CREATE TABLE IF NOT EXISTS novaky 
                      (user_id INTEGER PRIMARY KEY, name TEXT, meat INTEGER, 
                       exp INTEGER, energy INTEGER, last_rest INTEGER, 
                       is_sleeping INTEGER DEFAULT 0, photo_id INTEGER,
                       last_hunt INTEGER DEFAULT 0, last_train INTEGER DEFAULT 0)''')
    
    # НОВА ТАБЛИЦЯ ДЛЯ СТОСУНКІВ
    conn.execute('''CREATE TABLE IF NOT EXISTS relationships 
                      (user_one INTEGER, user_two INTEGER, points INTEGER, status TEXT,
                       PRIMARY KEY (user_one, user_two))''')
    
    # Безпечне додавання нових колонок, якщо база вже існувала
    try: conn.execute("ALTER TABLE novaky ADD COLUMN last_hunt INTEGER DEFAULT 0")
    except: pass
    try: conn.execute("ALTER TABLE novaky ADD COLUMN last_train INTEGER DEFAULT 0")
    except: pass
    conn.commit(); conn.close()

def get_and_refresh_novak(user_id):
    conn = sqlite3.connect('forest_novaky.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_hunt, last_train FROM novaky WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row: return None
    name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_hunt, last_train = row
    now = int(time.time())
    speed = 100 if is_sleeping else 300
    recovered = (now - last_rest) // speed
    if recovered > 0:
        energy = min(100, energy + recovered)
        conn.execute("UPDATE novaky SET energy = ?, last_rest = ? WHERE user_id = ?", (energy, now, user_id))
        conn.commit()
    conn.close()
    return {"name": name, "meat": meat, "exp": exp, "energy": energy, "is_sleeping": is_sleeping, "photo_id": photo_id, "last_hunt": last_hunt, "last_train": last_train}

def get_relation(u1, u2):
    p1, p2 = min(u1, u2), max(u1, u2)
    conn = sqlite3.connect('forest_novaky.db')
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
    
    status = current["status"]
    if set_status: status = set_status
    elif new_points >= 50 and status == "Знайомі": status = "Друзі"
    elif new_points <= -30 and status == "Знайомі": status = "Вороги"
    elif new_points > -30 and new_points < 50 and status in ["Друзі", "Вороги"]: status = "Знайомі"
    
    conn = sqlite3.connect('forest_novaky.db')
    conn.execute("INSERT OR REPLACE INTO relationships VALUES (?, ?, ?, ?)", (p1, p2, new_points, status))
    conn.commit(); conn.close()
    return {"points": new_points, "status": status}

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
                msg = update["message"]; text = msg["text"].lower(); cid = msg["chat"]["id"]; uid = msg["from"]["id"]
                
                n = get_and_refresh_novak(uid)
                
                if text == "/start":
                    if not n:
                        conn = sqlite3.connect('forest_novaky.db')
                        conn.execute("INSERT INTO novaky (user_id, name, meat, exp, energy, last_rest, is_sleeping, photo_id) VALUES (?,?,?,?,?,?,?,?)", 
                                   (uid, "Новак", 0, 0, 100, int(time.time()), 0, random.randint(1, TOTAL_PHOTOS)))
                        conn.commit(); conn.close()
                        send_msg(cid, "🌲 Новака знайдено! Напиши 'мій новак'.")
                    else: send_msg(cid, "🐾 У тебе вже є новак!")
                
                elif n:
                    if "мій новак" in text: send_profile(cid, n)
                    
                    # === СИСТЕМА СТОСУНКІВ (ЧЕРЕЗ REPLY) ===
                    elif text in ["подружитися", "покусати", "пара"]:
                        if "reply_to_message" not in msg:
                            send_msg(cid, "⚠️ Цю команду треба писати у відповідь (*reply*) на повідомлення іншого гравця!")
                            continue
                        
                        target_uid = msg["reply_to_message"]["from"]["id"]
                        if target_uid == uid:
                            send_msg(cid, "🐱 Ти не можеш будувати стосунки сам із собою!")
                            continue
                        
                        target_n = get_and_refresh_novak(target_uid)
                        if not target_n:
                            send_msg(cid, "🐾 Цей гравець ще не знайшов свого новака.")
                            continue
                        
                        if text == "подружитися":
                            res_rel = update_relation(uid, target_uid, 15)
                            send_msg(cid, f"🤝 **{n['name']}** виявив дружелюбність до **{target_n['name']}**!\n"
                                          f"💞 Рівень прихильності: {res_rel['points']}/100 Статус: *{res_rel['status']}*")
                        
                        elif text == "покусати":
                            res_rel = update_relation(uid, target_uid, -20)
                            send_msg(cid, f"😾 **{n['name']}** люто покусав **{target_n['name']}**!\n"
                                          f"💔 Рівень прихильності: {res_rel['points']}/100. Статус: *{res_rel['status']}*")
                        
                        elif text == "пара":
                            current_rel = get_relation(uid, target_uid)
                            if current_rel["points"] < 60:
                                send_msg(cid, f"❌ Стосунки занадто холодні ({current_rel['points']}/100). Потрібно хоча б 60 балів прихильності, щоб стати парою!")
                            else:
                                res_rel = update_relation(uid, target_uid, 10, set_status="Пара")
                                send_msg(cid, f"❤️ ✨ **{n['name']}** та **{target_n['name']}** тепер офіційно стали парою! ✨ ❤️")

                    elif text == "стосунки":
                        conn = sqlite3.connect('forest_novaky.db')
                        cursor = conn.cursor()
                        cursor.execute("SELECT user_one, user_two, points, status FROM relationships WHERE user_one=? OR user_two=?", (uid, uid))
                        all_rels = cursor.fetchall()
                        
                        if not all_rels:
                            send_msg(cid, "🍃 Твій новак ще ні з ким не перетинався в лісі.")
                        else:
                            rel_msg = f"📜 **Стосунки новака {n['name']}:**\n\n"
                            for r in all_rels:
                                other_id = r[1] if r[0] == uid else r[0]
                                cursor.execute("SELECT name FROM novaky WHERE user_id=?", (other_id,))
                                name_row = cursor.fetchone()
                                other_name = name_row[0] if name_row else "Невідомий кіт"
                                rel_msg += f"• з **{other_name}**: {r[2]}/100 Балів [*{r[3]}*]\n"
                            conn.close()
                            send_msg(cid, rel_msg)
                    
                    # === ІНШІ КОМАНДИ И ГРИ ===
                    elif "тренувати" in text:
                        now = int(time.time())
                        if now < n["last_train"] + 3600:
                            send_msg(cid, f"⏳ Новак втомлений. Зачекай {(n['last_train']+3600-now)//60} хв.")
                        elif n["is_sleeping"]: send_msg(cid, "💤 Новак спить!")
                        elif n["energy"] < 30: send_msg(cid, "🪫 Мало енергії (треба 30).")
                        else:
                            exp_gain = random.randint(20, 40)
                            conn = sqlite3.connect('forest_novaky.db')
                            conn.execute("UPDATE novaky SET exp=exp+?, energy=energy-30, last_train=? WHERE user_id=?", (exp_gain, now, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"⚔️ Тренування! Досвід: +{exp_gain} ✨. (-30🔋)")

                    elif text == "топ":
                        conn = sqlite3.connect('forest_novaky.db')
                        cursor = conn.cursor()
                        cursor.execute("SELECT name, exp FROM novaky ORDER BY exp DESC LIMIT 10")
                        leaders = cursor.fetchall()
                        conn.close()
                        leader_text = "🏆 **Рейтинг найкращих новаків:**\n\n"
                        for i, leader in enumerate(leaders, 1):
                            leader_text += f"{i}. {leader[0]} — {leader[1]} ✨\n"
                        send_msg(cid, leader_text)

                    elif "полювати" in text:
                        now = int(time.time())
                        if now < n["last_hunt"] + 3600:
                            send_msg(cid, f"⏳ Зачекай ще {(n['last_hunt']+3600-now)//60} хв.")
                        elif n["is_sleeping"]: send_msg(cid, "💤 Розбуди його!")
                        elif n["energy"] < 20: send_msg(cid, "🪫 Мало енергії (треба 20).")
                        else:
                            loc = random.choice([{"n": "🌲 Ліс", "m": 2, "e": 10}, {"n": "🏚️ Ферма", "m": 3, "e": 15}])
                            conn = sqlite3.connect('forest_novaky.db')
                            conn.execute("UPDATE novaky SET meat=meat+?, energy=energy-20, exp=exp+?, last_hunt=? WHERE user_id=?", (loc["m"], loc["e"], now, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"🏹 Полювання у **{loc['n']}**! +{loc['m']}кг м'яса.")

                    elif "спати" in text:
                        conn = sqlite3.connect('forest_novaky.db')
                        conn.execute("UPDATE novaky SET is_sleeping=1, last_rest=? WHERE user_id=?", (int(time.time()), uid))
                        conn.commit(); conn.close(); send_msg(cid, "💤 Новак ліг спати.")
                    elif "прокинутись" in text:
                        conn = sqlite3.connect('forest_novaky.db')
                        conn.execute("UPDATE novaky SET is_sleeping=0, last_rest=? WHERE user_id=?", (int(time.time()), uid))
                        conn.commit(); conn.close(); send_msg(cid, "☀️ Новак прокинувся!")
                    elif text.startswith("назви "):
                        new_name = update["message"]["text"][6:].strip()
                        if new_name:
                            conn = sqlite3.connect('forest_novaky.db')
                            conn.execute("UPDATE novaky SET name=? WHERE user_id=?", (new_name, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"✨ Тепер назва новака: **{new_name}**!")
                    elif "їсти" in text:
                        if n["meat"] > 0:
                            conn = sqlite3.connect('forest_novaky.db')
                            conn.execute("UPDATE novaky SET meat=meat-1, energy=min(100, energy+15) WHERE user_id=?", (uid,))
                            conn.commit(); conn.close(); send_msg(cid, "🍴 Смачно! +15🔋")
                        else: send_msg(cid, "🥩 Немає м'яса!")
        except: time.sleep(1)

if __name__ == '__main__': main()
