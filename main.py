import telebot
import os
import random
import time
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ТВІЙ ТОКЕН ВЖЕ ТУТ
TOKEN = '8738009781:AAFaG6aVZzAEoC_HvwoBry_-gFwNp6fhKU8'
bot = telebot.TeleBot(TOKEN)

app = Flask('')

@app.route('/')
def home():
    return "Бот активний!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Тимчасова база даних (працює поки бот запущений)
db = {}

# Список картинок (твоя папка на GitHub)
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
        db[user_id]['name'] = new_name
        bot.reply_to(message, f"✅ Тепер твого котика звати **{new_name}**!")

@bot.message_handler(func=lambda m: m.text.lower() == 'полювати')
def hunt(message):
    user_id = str(message.from_user.id)
    if user_id not in db: return

    update_energy(user_id)
    user = db[user_id]

    now = datetime.now()
    if user.get('last_hunt'):
        last_hunt_time = datetime.fromisoformat(user['last_hunt'])
        if now < last_hunt_time + timedelta(hours=1):
            wait = (last_hunt_time + timedelta(hours=1)) - now
            mins = int(wait.total_seconds() // 60)
            bot.reply_to(message, f"⏳ Новак втомлений. Зачекай ще {mins} хв.")
            return

    if user['energy'] < 20:
        bot.reply_to(message, "🪫 Мало енергії (треба хоча б 20%).")
        return
    
    if user['status'] == 'Спить':
        bot.reply_to(message, "💤 Спочатку напиши 'прокинутись'.")
        return

    loc = random.choice([
        {"name": "🌲 Густий ліс", "meat": random.randint(1, 3), "exp": 10},
        {"name": "🏚️ Стара ферма", "meat": random.randint(2, 4), "exp": 15}
    ])
    
    user['meat'] += loc['meat']
    user['experience'] += loc['exp']
    user['energy'] -= 20
    user['last_hunt'] = now.isoformat()
    
    bot.reply_to(message, f"🏹 Полювання у **{loc['name']}**!\nЗдобуто: {loc['meat']} кг м'яса! (+{loc['exp']} ✨)")

@bot.message_handler(func=lambda m: m.text.lower() == 'їсти')
def eat(message):
    user_id = str(message.from_user.id)
    if user_id in db:
        user = db[user_id]
        if user['meat'] > 0:
            user['meat'] -= 1
            user['energy'] = min(100, user['energy'] + 15)
            bot.reply_to(message, f"🍖 Смачно! Залишилось: {user['meat']} кг")
        else:
            bot.reply_to(message, "❌ Немає м'яса! Сходи на полювання.")

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
        bot.reply_to(message, "☀️ Новак прокинувся!")

keep_alive()
bot.polling(none_stop=True)
            
