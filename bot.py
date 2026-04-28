# bot.py - ИСПРАВЛЕННАЯ ВЕРСИЯ (БЕЗ ПОТОКОВ)
import os
import requests
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============= ТВОИ ДАННЫЕ =============
BOT_TOKEN = "8789024886:AAEoJN_Z1KqIQyiCgPsPgo6iGNpE-JvixHc"
ADMIN_IDS = [1288498341, 6893022735]
FLASK_API_URL = "https://genshin-farm.onrender.com/api/bot"
# =====================================

# Фейковое Flask-приложение для Render (для health check)
app_web = Flask(__name__)

@app_web.route('/')
def health():
    return "Bot is running", 200

# ============= ЛОГИКА БОТА =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            "🌟 *Genshin Farm Bot*\n\n"
            "📌 Отправь ссылку на FunPay - я добавлю заказ\n"
            "📌 Отправь ID заказа - узнаю кто взял",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Нет доступа")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    
    text = update.message.text.strip()
    
    if text.isdigit():
        await check_order_by_id(update, int(text))
    elif "funpay.com" in text:
        await add_order_by_url(update, text)
    else:
        await update.message.reply_text("❌ Отправь ссылку на FunPay или ID заказа")

async def add_order_by_url(update: Update, url: str):
    await update.message.reply_text("🔄 Добавляю заказ...")
    
    order_data = {
        'title': 'Заказ с FunPay',
        'description': f'Выполнить заказ: {url}',
        'reward': 150.0,
        'funpay_url': url
    }
    
    try:
        response = requests.post(f"{FLASK_API_URL}/add_order", json=order_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            await update.message.reply_text(
                f"✅ *Заказ добавлен!*\n\n"
                f"🆔 ID: {data.get('order_id')}\n"
                f"💰 Цена: 150₽",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ Ошибка: {response.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def check_order_by_id(update: Update, order_id: int):
    try:
        response = requests.get(f"{FLASK_API_URL}/order_info/{order_id}", timeout=5)
        
        if response.status_code == 200:
            order = response.json()
            
            status_emoji = {'new': '🆕', 'taken': '⚡', 'completed': '✅'}.get(order['status'], '❓')
            status_text = {'new': 'Новый', 'taken': 'В работе', 'completed': 'Выполнен'}.get(order['status'], order['status'])
            
            message = f"{status_emoji} *Заказ #{order['id']}*\n\n"
            message += f"📋 *Название:* {order['title']}\n"
            message += f"💰 *Цена:* {order['reward']}₽\n"
            message += f"📊 *Статус:* {status_text}\n"
            
            if order.get('taken_by'):
                message += f"\n👤 *Взял:* {order['taken_by']['username']}\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Заказ #{order_id} не найден")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# ============= ЗАПУСК =============
if __name__ == '__main__':
    # Запускаем Flask в отдельном потоке, а бота в главном
    from threading import Thread
    
    # Запускаем Flask сервер в фоне
    def run_flask():
        port = int(os.environ.get('PORT', 10000))
        app_web.run(host='0.0.0.0', port=port)
    
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    # Запускаем бота в главном потоке
    print("=" * 50)
    print("🤖 ЗАПУСК GENSHIN FARM BOT")
    print("=" * 50)
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"🌐 API URL: {FLASK_API_URL}")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Удаляем вебхук
    async def delete_webhook():
        await app.bot.delete_webhook(drop_pending_updates=True)
        print("✅ Вебхук удалён")
    
    asyncio.run(delete_webhook())
    
    print("✅ БОТ ЗАПУЩЕН! Ожидание сообщений...")
    app.run_polling()
