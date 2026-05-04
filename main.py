import telebot
import os
import random
import time
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# Твій токен вже вставлений
TOKEN = '8738009781:AAFaG6aVZzAEoC_HvwoBry_-gFwNp6fhKU8'
bot = telebot.TeleBot(TOKEN)

app = Flask('')

@app.route('/')
def home():
    return "I am alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# База даних у пам'яті
db = {}

# Список картинок
images = [f'my_shkets/cat{i}.jpg' for i in range(1, 11)]

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
    try:
        bot.send_photo(message.chat.id, open(db[user_id]['image'], 'rb'), 
                       caption="🐾 Вітаю! Твій новак готовий до пригод.\nПиши 'мій новак'.")
    except:
        bot.send_message(message.chat.id, "🐾 Вітаю! Твій новак готовий до пригод.\nПиши 'мій новак'.")

def update_energy(user_id):
    user = db[user_id]
    now = time.time()
    diff = (now - user['last_update']) / 60
    speed = 3.0 if user['status'] == 'Спить' else 1.0
    user['energy'] = min(100, user['energy'] + diff * speed)
    user['last_update'] = now

@bot.message_handler(func=lambda m: m.text.lower() == 'мій новак')
def status(message):
    user_id = str(message.from_user.id)
    if user_id in db:
        update_energy(user_id)
        user = db[user_id]
        msg = (f"🐱 **{user['name']}**\n"
               f"📊 Статус: {user['status']}\n"
               f"🔋 Енергія: {int(user['energy'])}%\n"
               f"🍖 М'ясо: {user['meat']} кг\n"
               f"✨ Досвід: {user['experience']}")
        try:
            bot.send_photo(message.chat.id, open(user['image'], 'rb'), caption=msg, parse_mode="Markdown")
        except:
            bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text.lower().startswith('назви '))
def rename(message):
    user_id = str(message.from_user.id)
    if user_id in db:
        new_name = message.text[6:].strip()
        db[user_id]['
        
