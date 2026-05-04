import requests, time, sqlite3, random, json, os
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "Новак працює: полювання раз на годину!"

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

TOKEN = '8738009781:AAFaG6aVZzAEoC_HvwoBry_-gFwNp6fhKU8'
URL = f'https://api.telegram.org/bot{TOKEN}/'
PHOTO_PATH = 'my_shkets/' 
TOTAL_PHOTOS = 20

def init_db():
    conn = sqlite3.connect('forest_novaky.db')
    # Створюємо таблицю з новою колонкою last_hunt
    conn.execute('''CREATE TABLE IF NOT EXISTS novaky 
                      (user_id INTEGER PRIMARY KEY, name TEXT, meat INTEGER, 
                       exp INTEGER, energy INTEGER, last_rest INTEGER, 
                       is_sleeping INTEGER DEFAULT 0, photo_id INTEGER,
                       last_hunt INTEGER DEFAULT 0)''')
    # Перевірка на випадок, якщо таблиця вже була без цієї колонки
    try:
        conn.execute("ALTER TABLE novaky ADD COLUMN last_hunt INTEGER DEFAULT 0")
    except:
        pass
    conn.commit(); conn.close()

def get_and_refresh_novak(user_id):
    conn = sqlite3.connect('forest_novaky.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_hunt FROM novaky WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row: return None
    name, meat, exp, energy, last_rest, is_sleeping, photo_id, last_hunt = row
    now = int(time.time())
    speed = 100 if is_sleeping else 300
    recovered = (now - last_rest) // speed
    if recovered > 0:
        energy = min(100, energy + recovered)
        conn.execute("UPDATE novaky SET energy = ?, last_rest = ? WHERE user_id = ?", (energy, now, user_id))
        conn.commit()
    conn.close()
    return {"name": name, "meat": meat, "exp": exp, "energy": energy, "is_sleeping": is_sleeping, "photo_id": photo_id, "last_hunt": last_hunt}

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
                        conn.execute("INSERT INTO novaky VALUES (?,?,?,?,?,?,?,?,?)", (uid,"Новак",0,0,100,int(time.time()),0,random.randint(1, TOTAL_PHOTOS), 0))
                        conn.commit(); conn.close()
                        send_msg(cid, "🌲 Новака знайдено! Напиши 'мій новак'.")
                    else: send_msg(cid, "🐾 У тебе вже є новак!")
                
                elif n:
                    if "мій новак" in text: send_profile(cid, n)
                    
                    elif "видалити новака" in text:
                        conn = sqlite3.connect('forest_novaky.db')
                        conn.execute("DELETE FROM novaky WHERE user_id=?", (uid,))
                        conn.commit(); conn.close()
                        send_msg(cid, "💨 Твого новака відпущено в ліс... Тепер ти можеш знайти нового через /start.")

                    elif "полювати" in text:
                        now = int(time.time())
                        # Перевірка на 1 годину (3600 секунд)
                        if now < n["last_hunt"] + 3600:
                            wait_mins = (n["last_hunt"] + 3600 - now) // 60
                            send_msg(cid, f"⏳ Новак ще не відпочив! Зачекай {max(1, wait_mins)} хв.")
                        elif n["is_sleeping"]: send_msg(cid, "💤 Твій новак спить! Спочатку розбуди його.")
                        elif n["energy"] < 20: send_msg(cid, "🪫 Мало енергії (треба хоча б 20).")
                        else:
                            # Система двох локацій
                            loc = random.choice([
                                {"name": "🌲 Густий ліс", "meat": random.randint(1, 3), "exp": 10},
                                {"name": "🏚️ Стара ферма", "meat": random.randint(2, 4), "exp": 15}
                            ])
                            conn = sqlite3.connect('forest_novaky.db')
                            conn.execute("UPDATE novaky SET meat=meat+?, energy=energy-20, exp=exp+?, last_hunt=? WHERE user_id=?", (loc["meat"], loc["exp"], now, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"🏹 Новак пішов у **{loc['name']}**.\nЗнайдено м'яса: {loc['meat']} кг. (+{loc['exp']}✨, -20🔋)")
                    
                    elif "спати" in text:
                        conn = sqlite3.connect('forest_novaky.db')
                        conn.execute("UPDATE novaky SET is_sleeping=1, last_rest=? WHERE user_id=?", (int(time.time()), uid))
                        conn.commit(); conn.close()
                        send_msg(cid, "💤 Новак влігся спати. Енергія відновлюється швидше!")
                    
                    elif "прокинутись" in text:
                        conn = sqlite3.connect('forest_novaky.db')
                        conn.execute("UPDATE novaky SET is_sleeping=0, last_rest=? WHERE user_id=?", (int(time.time()), uid))
                        conn.commit(); conn.close()
                        send_msg(cid, "☀️ Новак прокинувся і готовий до пригод!")
                    
                    elif text.startswith("назви "):
                        new_name = update["message"]["text"][6:].strip()
                        if new_name:
                            conn = sqlite3.connect('forest_novaky.db')
                            conn.execute("UPDATE novaky SET name=? WHERE user_id=?", (new_name, uid))
                            conn.commit(); conn.close()
                            send_msg(cid, f"✨ Тепер твого новака звати **{new_name}**!")
                    
                    elif "їсти" in text:
                        if n["meat"] > 0:
                            conn = sqlite3.connect('forest_novaky.db')
                            conn.execute("UPDATE novaky SET meat=meat-1, energy=min(100, energy+15) WHERE user_id=?", (uid,))
                            conn.commit(); conn.close(); send_msg(cid, "🍴 Смачно! +15🔋")
                        else: send_msg(cid, "🥩 У тебе немає м'яса. Сходи на полювання!")
        except: time.sleep(1)

if __name__ == '__main__': main()
    
