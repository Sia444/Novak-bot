import requests, time, sqlite3, random, json, os, datetime
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "Бот Квестів та Лисиць працює!"

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

TOKEN = '8738009781:AAGsaGihufi6das9Xk89eUl3rwF-J6GS-xc'
URL = f'https://api.telegram.org/bot{TOKEN}/'
PHOTO_PATH = 'my_shkets/' 
TOTAL_PHOTOS = 20
DB_NAME = 'forest_novaky_v4.db'

QUEST_TYPES = {
    1: {"type": "meat", "desc": "🥩 Вполювати від 1 до 4 кг м'яса для Клану", "energy": 25},
    2: {"type": "elders", "desc": "🦔 Допомога старійшинам Клану", "energy": 50, "exp": 30},
    3: {"type": "moss", "desc": "🌿 Назбирати від 1 до 3 кг моху для підстилок", "energy": 25},
    4: {"type": "patrol", "desc": "🐾 Відправитись у патрулювання кордонів", "energy": 50, "exp": 40}
}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS novaky 
                      (user_id INTEGER PRIMARY KEY, name TEXT, meat INTEGER, 
                       exp INTEGER, energy INTEGER, last_rest INTEGER, 
                       is_sleeping INTEGER DEFAULT 0, photo_id INTEGER,
                       last_hunt INTEGER DEFAULT 0, last_train INTEGER DEFAULT 0,
                       last_rel INTEGER DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS relationships 
                      (user_one INTEGER, user_two INTEGER, points INTEGER, status TEXT,
                       PRIMARY KEY (user_one, user_two))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS user_quests 
                      (user_id INTEGER PRIMARY KEY, date TEXT,
                       q1_id INTEGER, q1_target INTEGER, q1_current INTEGER, q1_done INTEGER,
                       q2_id INTEGER, q2_target INTEGER, q2_current INTEGER, q2_done INTEGER)''')
    conn.commit(); conn.close()

def get_today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def generate_daily_quests(user_id):
    today = get_today_str()
    chosen_ids = random.sample([1, 2, 3, 4], 2)
    q1_id = chosen_ids[0]
    q1_target = random.randint(1, 4) if q1_id == 1 else (random.randint(1, 3) if q1_id == 3 else 0)
    q2_id = chosen_ids[1]
    q2_target = random.randint(1, 4) if q2_id == 1 else (random.randint(1, 3) if q2_id == 3 else 0)
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''INSERT OR REPLACE INTO user_quests 
                    (user_id, date, q1_id, q1_target, q1_current, q1_done, q2_id, q2_target, q2_current, q2_done) 
                    VALUES (?, ?, ?, ?, 0, 0, ?, ?, 0, 0)''', 
                 (user_id, today, q1_id, q1_target, q2_id, q2_target))
    conn.commit(); conn.close()

def get_user_quests(user_id):
    today = get_today_str()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT date, q1_id, q1_target, q1_current, q1_done, q2_id, q2_target, q2_current, q2_done FROM user_quests WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or row[0] != today:
        generate_daily_quests(user_id)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT date, q1_id, q1_target, q1_current, q1_done, q2_id, q2_target, q2_current, q2_done FROM user_quests WHERE user_id=?", (user_id,))
        row = cursor.fetchone()
        conn.close()
    return {
        "q1": {"id": row[1], "target": row[2], "current": row[3], "done": row[4]},
        "q2": {"id": row[5], "target": row[6], "current": row[7], "done": row[8]}
    }

def update_quest_progress(user_id, quest_num, current, done):
    conn = sqlite3.connect(DB_NAME)
    if quest_num == 1:
        conn.execute("UPDATE user_quests SET q1_current=?, q1_done=? WHERE user_id=?", (current, done, user_id))
    else:
        conn.execute("UPDATE user_quests SET q2_current=?, q2_done=? WHERE user_id=?", (current, done, user_id))
    conn.commit(); conn.close()

def get_and_refresh_novak(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_hunt, last_train, last_rel FROM novaky WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row: return None
    name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_hunt, last_train, last_rel = row
    now = int(time.time())
    speed = 100 if is_sleeping else 300
    recovered = (now - last_rest) // speed
    if recovered > 0:
        energy = min(100, energy + recovered)
        conn.execute("UPDATE novaky SET energy = ?, last_rest = ? WHERE user_id = ?", (energy, now, user_id))
        conn.commit()
    conn.close()
    return {"name": name, "meat": meat, "exp": exp, "energy": energy, "is_sleeping": is_sleeping, "photo_id": photo_id, "last_hunt": last_hunt, "last_train": last_train, "last_rel": last_rel}

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
    status = current["status"]
    if set_status: status = set_status
    elif new_points >= 50 and status == "Знайомі": status = "Друзі"
    elif new_points <= -30 and status == "Знайомі": status = "Вороги"
    elif new_points > -30 and new_points < 50 and status in ["Друзі", "Вороги"]: status = "Знайомі"
    conn = sqlite3.connect(DB_NAME)
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
                msg = update["message"]; text = msg["text"].lower().strip(); cid = msg["chat"]["id"]; uid = msg["from"]["id"]
                n = get_and_refresh_novak(uid)
                
                if text == "/start":
                    if not n:
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("INSERT INTO novaky (user_id, name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_hunt, last_train, last_rel) VALUES (?,?,?,?,?,?,?,?,?,?,?)", 
                                   (uid, "Новак", 0, 0, 100, int(time.time()), 0, random.randint(1, TOTAL_PHOTOS), 0, 0, 0))
                        conn.commit(); conn.close()
                        generate_daily_quests(uid)
                        send_msg(cid, "🌲 Новака знайдено! Напиши 'мій новак'.")
                    else: send_msg(cid, "🐾 У тебе вже є новак!")
                    
                elif n:
                    if "мій новак" in text: 
                        send_profile(cid, n)
                        
                    elif text == "завдання":
                        quests = get_user_quests(uid)
                        def format_quest(q, num):
                            inf = QUEST_TYPES[q["id"]]
                            if q["done"]: return f"{num}. {inf['desc']} — ✅ **Виконано!**"
                            if inf["type"] in ["meat", "moss"]:
                                return f"{num}. {inf['desc']} — 🎒 Зібрано: **{q['current']}/{q['target']} кг**. (⚡ Енергія: {inf['energy']})"
                            return f"{num}. {inf['desc']} — ❌ Не виконано. (⚡ Енергія: {inf['energy']})"
                        msg_text = f"📜 **Щоденні квести для кота {n['name']}:**\n\n"
                        msg_text += format_quest(quests["q1"], 1) + "\n\n"
                        msg_text += format_quest(quests["q2"], 2) + "\n\n"
                        msg_text += "💡 Щоб виконати завдання, напиши: `завдання 1` або `завдання 2`"
                        send_msg(cid, msg_text)
                        
                    elif text in ["завдання 1", "завдання 2"]:
                        if n["is_sleeping"]:
                            send_msg(cid, "💤 Кіт спить! Розбуди його спочатку.")
                            continue
                        quest_num = 1 if text == "завдання 1" else 2
                        quests = get_user_quests(uid)
                        q_data = quests["q1"] if quest_num == 1 else quests["q2"]
                        q_info = QUEST_TYPES[q_data["id"]]
                        if q_data["done"]:
                            send_msg(cid, "✅ Це завдання вже повністю виконано сьогодні!")
                            continue
                        if n["energy"] < q_info["energy"]:
                            send_msg(cid, f"🪫 Не вистачає енергії! Потрібно {q_info['energy']} ⚡, а у тебе лише {n['energy']}.")
                            continue
                        if q_info["type"] in ["meat", "moss"] and random.random() < 0.15:
                            loss_exp = random.randint(10, 30)
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("UPDATE novaky SET energy=max(0, energy-?), exp=max(0, exp-?) WHERE user_id=?", (q_info["energy"], loss_exp, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"🦊 **Жах!** У кущах твій новак нарвався на **лисицю**! 🦊\nВін ледве втік, розгубивши все зібране. Завдання провалено, кіт втратив {q_info['energy']} ⚡ енергії та -{loss_exp} ✨ досвіду!")
                            continue
                        if q_info["type"] in ["meat", "moss"]:
                            gain = random.randint(1, 3)
                            new_current = min(q_data["target"], q_data["current"] + gain)
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("UPDATE novaky SET energy=energy-? WHERE user_id=?", (q_info["energy"], uid))
                            conn.commit(); conn.close()
                            item_name = "кг м'яса" if q_info["type"] == "meat" else "кг моху"
                            emoji = "🥩" if q_info["type"] == "meat" else "🌿"
                            if new_current >= q_data["target"]:
                                exp_reward = random.randint(10, 30) if q_info["type"] == "meat" else random.randint(5, 25)
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("UPDATE novaky SET exp=exp+? WHERE user_id=?", (exp_reward, uid))
                                conn.commit(); conn.close()
                                update_quest_progress(uid, quest_num, new_current, 1)
                                send_msg(cid, f"{emoji} Твій новак приніс ще +{gain} {item_name} і повністю закрив завдання! 🎉\n📈 Нагорода: **+{exp_reward} досвіду**! (-{q_info['energy']} ⚡)")
                            else:
                                update_quest_progress(uid, quest_num, new_current, 0)
                                send_msg(cid, f"{emoji} Успішно! Новак приніс +{gain} {item_name}.\n🎒 Прогрес завдання: {new_current}/{q_data['target']} кг. (-{q_info['energy']} ⚡)")
                        else:
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("UPDATE novaky SET energy=energy-?, exp=exp+? WHERE user_id=?", (q_info["energy"], q_info["exp"], uid))
                            conn.commit(); conn.close()
                            update_quest_progress(uid, quest_num, 0, 1)
                            action_text = "допоміг старійшинам Клану, почистивши їм кубла від бліх" if q_info["type"] == "elders" else "успішно обійшов кордони території й оновив запахові мітки"
                            send_msg(cid, f"✅ **Завдання виконано!**\n🐾 Твій новак {action_text}.\n📈 Нагорода: **+{q_info['exp']} досвіду**! (-{q_info['energy']} ⚡)")
                            
                    elif "полювати" in text:
                        now = int(time.time())
                        if now < n["last_hunt"] + 3600:
                            send_msg(cid, f"⏳ Зачекай ще {(n['last_hunt']+3600-now)//60} хв.")
                        elif n["is_sleeping"]: send_msg(cid, "💤 Розбуди його!")
                        elif n["energy"] < 20: send_msg(cid, "🪫 Мало енергії (треба 20).")
                        else:
                            if random.random() < 0.15:
                                loss_exp = random.randint(10, 30)
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("UPDATE novaky SET energy=max(0, energy-20), exp=max(0, exp-?), last_hunt=? WHERE user_id=?", (loss_exp, now, uid))
                                conn.commit(); conn.close()
                                send_msg(cid, f"🦊 **О ні, лисиця!** Під час полювання твій новак наткнувся на хижака.\nЗдобич втрачено, кіт отримав подряпини: -20 ⚡ енергії та -{loss_exp} ✨ досвіду.")
                                continue
                            loc = random.choice([{"n": "🌲 Ліс", "m": 2, "e": 10}, {"n": "🏚️ Ферма", "m": 3, "e": 15}])
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("UPDATE novaky SET meat=meat+?, energy=energy-20, exp=exp+?, last_hunt=? WHERE user_id=?", (loc["m"], loc["e"], now, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"🏹 Полювання у **{loc['n']}**! +{loc['m']}кг м'яса для себе.")
                            
                    elif text in ["подружитися", "покусати", "пара"]:
                        if "reply_to_message" not in msg:
                            send_msg(cid, "⚠️ Цю команду треба писати у відповідь (*reply*) на повідомлення іншого гравця!")
                            continue
                        target_uid = msg["reply_to_message"]["from"]["id"]
                        if target_uid == uid:
                            send_msg(cid, "🐱 Ти не можеш взаємодіяти сам із собою!")
                            continue
                        target_n = get_and_refresh_novak(target_uid)
                        if not target_n:
                            send_msg(cid, "🐾 Цей гравець ще не знайшов свого новака.")
                            continue
                        now = int(time.time())
                        if now < n["last_rel"] + 3600:
                            left_min = (n["last_rel"] + 3600 - now) // 60
                            send_msg(cid, f"⏳ Твій новак втомлений. Зачекай ще {left_min} хв для нових стосунків.")
                            continue
                        if text == "подружитися":
                            res_rel = update_relation(uid, target_uid, 15)
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("UPDATE novaky SET last_rel=? WHERE user_id=?", (now, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"🤝 **{n['name']}** виявив дружелюбність до **{target_n['name']}**!\n💞 Прихильність: {res_rel['points']}/100. Status: *{res_rel['status']}*")
                        elif text == "покусати":
                            res_rel = update_relation(uid, target_uid, -20)
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("UPDATE novaky SET last_rel=? WHERE user_id=?", (now, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"😾 **{n['name']}** люто покусав **{target_n['name']}**!\n💔 Прихильність: {res_rel['points']}/100. Status: *{res_rel['status']}*")
                        elif text == "пара":
                            current_rel = get_relation(uid, target_uid)
                            if current_rel["points"] < 60:
                                send_msg(cid, f"❌ Стосунки занадто холодні ({current_rel['points']}/100). Потрібно хоча б 60 балів!")
                            else:
                                res_rel = update_relation(uid, target_uid, 10, set_status="Пара")
                                conn = sqlite3.connect(DB_NAME)
                                conn.execute("UPDATE novaky SET last_rel=? WHERE user_id=?", (now, uid))
                                conn.commit(); conn.close()
                                send_msg(cid, f"❤️ ✨ **{n['name']}** та **{target_n['name']}** тепер офіційно стали парою! ✨ ❤️")
                                
                    elif text == "топ":
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("SELECT name, exp FROM novaky ORDER BY exp DESC LIMIT 10")
                        leaders = cursor.fetchall()
                        conn.close()
                        leader_text = "🏆 **Рейтинг найкращих новаків:**\n\n"
                        for i, leader in enumerate(leaders, 1):
                            leader_text += f"{i}. {leader[0]} — {leader[1]} ✨\n"
                        send_msg(cid, leader_text)
                        
                    elif text.startswith("назви "):
                        new_name = update["message"]["text"][6:].strip()
                        if new_name:
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("UPDATE novaky SET name=? WHERE user_id=?", (new_name, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"✨ Тепер назва новака: **{new_name}**!")
                            
                    elif "спати" in text:
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE novaky SET is_sleeping=1, last_rest=? WHERE user_id=?", (int(time.time()), uid))
                        conn.commit(); conn.close(); send_msg(cid, "💤 Новак ліг спати. Енергія тепер відновлюється швидше!")
                        
                    elif "прокинутись" in text:
                        conn = sqlite3.connect(DB_NAME)
                        conn.execute("UPDATE novaky SET is_sleeping=0, last_rest=? WHERE user_id=?", (int(time.time()), uid))
                        conn.commit(); conn.close(); send_msg(cid, "☀️ Новак прокинувся і готовий до пригод!")

                    elif "їсти" in text:
                        if n["meat"] > 0:
                            conn = sqlite3.connect(DB_NAME)
                            conn.execute("UPDATE novaky SET meat=meat-1, energy=min(100, energy+15) WHERE user_id=?", (uid,))
                            conn.commit(); conn.close(); send_msg(cid, "🍴 Смачно пообідав м'ясом! +15 🔋 енергії.")
                        else: send_msg(cid, "🥩 Немає м'яса!")

        except Exception as e:
            print(f"Помилка в циклі: {e}")
            time.sleep(1)

if __name__ == '__main__':
    main()
    
