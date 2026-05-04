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
    return "Бот активний та запінгований!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Функція для самопінгу (щоб Render не вимикав бота)
def ping_self():
    while True:
        try:
            # Заміни посилання на своє, якщо воно відрізняється
            requests.get("https://novak-bot.onrender.com")
        except:
            print("Помилка пінгу")
        time.sleep(300) # Кожні 5 хвилин

# Тимчасова база даних
db = {}
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
        db[user_id] = {'name': 'Новак', 'meat': 0, 'energy': 100, 'experience': 0, 'status': 'Гуляє', 'last_update': time.time(), 'last_hunt': None, 'image': random.choice(images)}
    bot.reply_to(message, "🐾 Новак готовий! Пиши 'мій новак'.")

@bot.message_handler(func=lambda m: m.text.lower() == 'мій новак')
def status(message):
    user_id = str(message.from_user.id)
    if user_id in db:
        update_energy(user_id)
        user = db[user_id]
        msg = f"🐱 **{user['name']}**\n📊 Статус: {user['status']}\n🔋 Енергія: {int(user['energy'])}%\n🍖 М'ясо: {user['meat']} кг"
        bot.reply_to(message, msg, parse_mode="Markdown")

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
            bot.reply_to(message, f"⏳ Зачекай ще {int(wait.total_seconds() // 60)} хв.")
            return

    if user['energy'] < 20:
        bot.reply_to(message, "🪫 Мало енергії!")
        return

    loc = random.choice([{"n": "🌲 Густий ліс", "m": 2}, {"n": "🏚️ Стара ферма", "m": 3}])
    user['meat'] += loc['m']
    user['energy'] -= 20
    user['last_hunt'] = now.isoformat()
    bot.reply_to(message, f"🏹 Полювання у **{loc['n']}**! Знайдено {loc['m']} кг м'яса.")

@bot.message_handler(func=lambda m: m.text.lower() == 'спати')
def sleep(message):
    user_id = str(message.from_user.id)
    if user_id in db:
        db[user_id]['status'] = 'Спить'
        bot.reply_to(message, "💤 Котик ліг спати.")

@bot.message_handler(func=lambda m: m.text.lower() == 'прокинутись')
def wake(message):
    user_id = str(message.from_user.id)
    if user_id in db:
        db[user_id]['status'] = 'Гуляє'
        bot.reply_to(message, "☀️ Котик прокинувся!")

if __name__ == "__main__":
    keep_alive()
    # Запускаємо пінг у окремому потоці
    Thread(target=ping_self).start()
    bot.polling(none_stop=True)
    
