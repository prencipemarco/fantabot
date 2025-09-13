import requests
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import time
import json
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("API_KEY")
USER_FILE = "users.json"

bot = Bot(token=TELEGRAM_TOKEN)

# === GESTIONE UTENTI ===
try:
    with open(USER_FILE, "r") as f:
        users = set(json.load(f))
except:
    users = set()

def save_users():
    with open(USER_FILE, "w") as f:
        json.dump(list(users), f)

def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    users.add(chat_id)
    save_users()
    update.message.reply_text("✅ Ti sei registrato agli avvisi Serie A! Riceverai notifiche a inizio e fine giornata.")

# === INVIO MESSAGGI ===
def send_to_all(text):
    for user in list(users):
        try:
            bot.send_message(chat_id=user, text=text)
        except:
            users.remove(user)
    save_users()

# === FUNZIONI SERIE A ===
def get_matches():
    url = "https://api.football-data.org/v4/competitions/2019/matches"
    headers = {"X-Auth-Token": API_KEY}
    response = requests.get(url, headers=headers)
    data = response.json()
    return data["matches"]

def get_next_round():
    matches = get_matches()
    future_matches = [m for m in matches if datetime.datetime.fromisoformat(m["utcDate"][:-1]) > datetime.datetime.now()]
    if not future_matches:
        return None, None, None
    giornata = future_matches[0]["matchday"]
    giornata_matches = [m for m in matches if m["matchday"] == giornata]
    start_time = datetime.datetime.fromisoformat(min(m["utcDate"] for m in giornata_matches)[:-1])
    end_time = datetime.datetime.fromisoformat(max(m["utcDate"] for m in giornata_matches)[:-1]) + datetime.timedelta(hours=2)
    return giornata, start_time, end_time

# === PROGRAMMAZIONE ===
scheduler = BackgroundScheduler()

def schedule_next_round():
    giornata, start, end = get_next_round()
    if not giornata:
        print("📭 Nessuna giornata trovata.")
        return
    
    print(f"📅 Prossima giornata {giornata}: start={start}, end={end}")

    scheduler.add_job(lambda: send_to_all(f"⚽ Giornata {giornata} di Serie A iniziata! 🔒 Mercato FANTACALCIO CHIUSO."),
                      'date', run_date=start)
    scheduler.add_job(lambda: giornata_finished(giornata),
                      'date', run_date=end)

def giornata_finished(giornata):
    send_to_all(f"✅ La giornata {giornata} è terminata! 🔓 Da domani mercato FANTACALCIO RIAPERTO.")
    schedule_next_round()  # Programma la giornata successiva

# === MAIN ===
if __name__ == "__main__":
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))

    schedule_next_round()
    scheduler.start()

    updater.start_polling()
    updater.idle()
