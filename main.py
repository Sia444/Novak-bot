import telebot
import os
import random
import time
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ТВІЙ ТОКЕН
TOKEN = '8738009781:AAFaG6aVZzAEoC_HvwoBry_-gFwNp6fhKU8'
bot = telebot.TeleBot(TOKEN)

app = Flask('')

@app.route('/')
def home():
    return "Новак-бот з фото працює!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

def ping_self():
    while True:
        try:
            requests.get("https://novak-bot.onrender.com")
        except:
            pass
        time.sleep(300)

# Тимчасова база даних
db = {}

# Список твоїх фото (мають бути в папці my_shkets на GitHub)
images = [f'my_shkets/cat{i}.jpg' for i in range(1, 11)]

def update_energy(user_id):
    user = db[user_id]
    now = time.time()
    diff = (now - user['last_update']) / 60
    speed = 3.0 if user['status'] == 'Спить' else 1.0
    user['energy'] = min(100, user['energy'] + diff * speed)
    user['last_update'] = now

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id not in db:
        db[user_id] = {
            'name': 'Новак',
            'meat': 0,
            'energy': 100,
            'experience': 0,
            'status': 'Гуляє',
            'last_update': time.time(),
            'last_hunt': None,
            'image': random.choice(images)
        }
    
    user = db[user_id]
    try:
        with open(user['image'], 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption="🐾 Вітаю! Твій новак готовий до пригод.\nПиши 'мій новак'.")
    except:
        bot.send_message(message.chat.id, "🐾 Вітаю! Твій новак готовий.\n(Не вдалося завантажити фото з папки my_shkets)")

@bot.message_handler(func=lambda m: m.text.lower() == 'мій новак')
def status(message):
    user_id = str(message.from_user.id)
    if user_id in db:
        update_energy(user_id)
        user = db[user_id]
        msg = (f"🐱 **{user['name']}**\n"
               f"📊 Статус: {user['status']}\n"
               f"🔋 Енергія: {int(user['energy'])}%\n"
               f"🍖 М'ясо: {user['meat']} кг")
        try:
            with open(user['image'], 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption=msg, parse_mode="Markdown")
        except:
            bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text.lower() == 'полювати')
def hunt(message):
    user_id = str(message.from_user.id)
    if user_id not in db: return
    update_energy(user_id)
    user = db[user_id]
    now = datetime.now()

    if user.get('last_hunt'):
        last = datetime.fromisoformat(user['last_hunt'])
        if now < last + timedelta(hours=1):
            wait = (last + timedelta(hours=1)) - now
            bot.reply_to(message, f"⏳ Твій новак втомлений. Зачекай ще {int(wait.total_seconds() // 60)} хв.")
            return

    if user['energy'] < 20:
        bot.reply_to(message, "🪫 Мало енергії! Відправ кота спати.")
        return

    loc = random.choice([{"n": "🌲 Густий ліс", "m": 2}, {"n": "🏚️ Стара ферма", "m": 3}])
    user['meat'] += loc['m']
    user['energy'] -= 20
    user['last_hunt'] = now.isoformat()
    bot.reply_to(message, f"🏹 Полювання у **{loc['n']}**!\nЗнайдено {loc['m']} кг м'яса! 🐾")

@bot.message_handler(func=lambda m: m.text.lower() == 'спати')
def sleep(message):
    user_id = str(message.from_user.id)
    if user_id in db:
        db[user_id]['status'] = 'Спить'
        bot.reply_to(message, "💤 Новак ліг спати. Енергія відновлюється швидше!")

@bot.message_handler(func=lambda m: m.text.lower() == 'прокинутись')
def wake(message):
    user_id = str(message.from_user.id)
    if user_id in db:
        db[user_id]['status'] = 'Гуляє'
        bot.reply_to(message, "☀️ Новак прокинувся і готовий до пригод!")

if __name__ == "__main__":
    keep_alive()
    Thread(target=ping_self).start()
    bot.polling(none_stop=True)
    
