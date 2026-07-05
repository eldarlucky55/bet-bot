import telebot
import time
import requests
import schedule
from datetime import datetime

# === КОНФИГ ===
BOT_TOKEN = "8312043374:AAHHGsRHFSYqZ5D0JMKUGCrqpYArE-0DZKQ"
API_KEY = "bcd7c5ef1a4fdc195c5370c95e0ffee9a6c9448769de463e648f05dadfc86b37"
BANK_PERCENT = 0.018
MAX_PICKS = 3
MIN_ODDS = 1.70
MAX_ODDS = 2.30

user_bankrolls = {}

bot = telebot.TeleBot(BOT_TOKEN)

# === ПРИНУДИТЕЛЬНЫЙ СБРОС WEBHOOK ===
try:
    import requests
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    print("✅ Webhook сброшен")
except Exception as e:
    print(f"⚠️ Ошибка сброса webhook: {e}")

# === СБРОС WEBHOOK ===
try:
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
    time.sleep(1)
except:
    pass

# === ЗАГЛУШКА ДЛЯ ТЕСТА (пока API не работает) ===
def get_mock_games():
    return [
        {"home_team": "LA Dodgers", "away_team": "SF Giants",
         "bookmakers": [{"markets": [{"outcomes": [{"price": 1.90}, {"price": 2.10}]}]}]},
        {"home_team": "NY Yankees", "away_team": "Boston Red Sox",
         "bookmakers": [{"markets": [{"outcomes": [{"price": 1.75}, {"price": 2.20}]}]}]},
        {"home_team": "Djokovic", "away_team": "Alcaraz",
         "bookmakers": [{"markets": [{"outcomes": [{"price": 1.60}, {"price": 2.30}]}]}]}
    ]

def fetch_games_from_api():
    try:
        sport = "baseball_mlb"
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={API_KEY}&regions=us&markets=h2h"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            games = []
            for event in data:
                home_team = event.get('home_team', 'Unknown')
                away_team = event.get('away_team', 'Unknown')
                outcomes = event.get('bookmakers', [{}])[0].get('markets', [{}])[0].get('outcomes', [])
                if len(outcomes) == 2:
                    home_odds = outcomes[0].get('price', 1.0)
                    away_odds = outcomes[1].get('price', 1.0)
                    games.append({
                        "home_team": home_team,
                        "away_team": away_team,
                        "bookmakers": [{"markets": [{"outcomes": [{"price": home_odds}, {"price": away_odds}]}]}]
                    })
            return games
        else:
            print(f"⚠️ Ошибка API: {response.status_code}. Использую тестовые данные.")
            return get_mock_games()
    except Exception as e:
        print(f"⚠️ Ошибка запроса: {e}. Использую тестовые данные.")
        return get_mock_games()

# === СТРАТЕГИИ ===
def get_top_picks(bankroll):
    games = fetch_games_from_api()
    picks = []
    for game in games:
        try:
            outcomes = game['bookmakers'][0]['markets'][0]['outcomes']
            home_odds = outcomes[0]['price']
            away_odds = outcomes[1]['price']
            if home_odds < away_odds:
                favorite = game['home_team']
                odds = home_odds
            else:
                favorite = game['away_team']
                odds = away_odds
            if MIN_ODDS <= odds <= MAX_ODDS:
                picks.append({
                    "match": f"{game['home_team']} vs {game['away_team']}",
                    "bet": f"F5 Moneyline на {favorite}",
                    "odds": odds,
                    "stake": round(bankroll * BANK_PERCENT, 2)
                })
        except:
            continue
    picks.sort(key=lambda x: x['odds'], reverse=True)
    return picks[:MAX_PICKS]

# === КОМАНДЫ ТЕЛЕГРАМ ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message,
        "🎯 Привет! Я твой спортивный аналитик.\n"
        "📊 Стратегии: Теннис (тоталы) + MLB (F5 Moneyline).\n\n"
        "Команды:\n"
        "/bank XXX - установить банк\n"
        "/today - получить ТОП-3 ставки\n"
        "/status - показать текущий банк"
    )

@bot.message_handler(commands=['bank'])
def set_bank(message):
    try:
        amount = float(message.text.split()[1])
        user_bankrolls[message.chat.id] = amount
        bot.reply_to(message, f"✅ Банк установлен: {amount:,.0f} ₸")
    except:
        bot.reply_to(message, "❌ Используй: /bank 1938320")

@bot.message_handler(commands=['status'])
def status(message):
    chat_id = message.chat.id
    if chat_id in user_bankrolls:
        bot.reply_to(message, f"💰 Текущий банк: {user_bankrolls[chat_id]:,.0f} ₸")
    else:
        bot.reply_to(message, "⚠️ Банк не установлен. Используй /bank")

@bot.message_handler(commands=['today'])
def get_today(message):
    chat_id = message.chat.id
    if chat_id not in user_bankrolls:
        bot.reply_to(message, "⚠️ Сначала установи банк командой /bank")
        return
    bank = user_bankrolls[chat_id]
    picks = get_top_picks(bank)
    if not picks:
        bot.reply_to(message, "📭 На сегодня явных ставок не найдено.")
        return
    response = f"📊 ТОП-{len(picks)} ставок на {datetime.now().strftime('%d.%m.%Y')}:\n\n"
    for i, pick in enumerate(picks, 1):
        response += f"{i}. {pick['match']}\n   🎯 {pick['bet']} (коэф. {pick['odds']})\n   💰 {pick['stake']:,.0f} ₸\n\n"
    bot.reply_to(message, response)

# === ЗАПУСК ===
# === АВТОМАТИЧЕСКАЯ РАССЫЛКА В 12:00 ===
def send_daily_picks():
    chat_id = None
    # Берём первый попавшийся chat_id из сохранённых
    if user_bankrolls:
        chat_id = list(user_bankrolls.keys())[0]
    if chat_id is None:
        print("⚠️ Нет активных чатов для рассылки")
        return
    bank = user_bankrolls.get(chat_id, 1938320)
    picks = get_top_picks(bank)
    if not picks:
        bot.send_message(chat_id, "📭 На сегодня явных ставок не найдено.")
        return
    response = f"📊 ЕЖЕДНЕВНЫЙ ПРОГНОЗ на {datetime.now().strftime('%d.%m.%Y')} (12:00):\n\n"
    for i, pick in enumerate(picks, 1):
        response += f"{i}. {pick['match']}\n   🎯 {pick['bet']} (коэф. {pick['odds']})\n   💰 {pick['stake']:,.0f} ₸\n\n"
    bot.send_message(chat_id, response)
    print(f"✅ Прогноз отправлен в {datetime.now().strftime('%H:%M')}")
if __name__ == "__main__":
    print("🚀 Бот запущен и работает...")
    print("🏸 Активные виды спорта: baseball_mlb, tennis_atp")
    print("⏰ Ежедневная рассылка настроена на 12:00")

    # Планируем ежедневную рассылку в 12:00
    schedule.every().day.at("12:00").do(send_daily_picks)

    # Запускаем бота и планировщик в одном цикле
    while True:
        try:
            schedule.run_pending()
            bot.polling(non_stop=True, interval=1, timeout=60)
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            time.sleep(10)