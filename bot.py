# bot.py - ИСПРАВЛЕННАЯ ВЕРСИЯ (РАБОТАЕТ 100%)
import os
import requests
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============= ТВОИ ДАННЫЕ =============
BOT_TOKEN = "8789024886:AAEoJN_Z1KqIQyiCgPsPgo6iGNpE-JvixHc"
ADMIN_IDS = [1288498341, 6893022735]
FLASK_API_URL = "https://genshin-farm.onrender.com/api/bot"
# =====================================

# Фейковое Flask-приложение для Render
app_web = Flask(__name__)

@app_web.route('/')
def health_check():
    return "🤖 Bot is running!", 200

@app_web.route('/health')
def health():
    return "OK", 200

# ============= ТЕЛЕГРАМ БОТ =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            "🌟 *Genshin Farm Bot*\n\n"
            "📌 *Доступные команды:*\n"
            "• Отправь ссылку на FunPay - я добавлю заказ\n"
            "• Отправь ID заказа - узнаю кто взял\n\n"
            "📌 *Пример ссылки:*\n"
            "https://funpay.com/orders/12345\n\n"
            "📌 *Пример ID:*\n"
            "5",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ У вас нет доступа к этому боту")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    
    text = update.message.text.strip()
    
    # Если это ID заказа (цифра)
    if text.isdigit():
        await check_order_by_id(update, int(text))
        return
    
    # Если это ссылка на FunPay
    if "funpay.com" in text:
        await add_order_by_url(update, text)
        return
    
    await update.message.reply_text(
        "❌ Отправь ссылку на FunPay (например, https://funpay.com/orders/12345)\n"
        "или ID заказа (например, 5)"
    )

async def add_order_by_url(update: Update, url: str):
    await update.message.reply_text("🔄 Создаю заказ...")
    
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
                f"💰 Цена: 150₽\n\n"
                f"💡 Качеры могут взять его в работу",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ Ошибка: {response.text}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка подключения к серверу: {str(e)}")

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
            message += f"📝 *Описание:* {order['description'][:150]}...\n"
            
            if order.get('taken_by'):
                message += f"\n👤 *Взял:* {order['taken_by']['username']}\n"
                if order.get('taken_at'):
                    message += f"⏰ *Время:* {order['taken_at']}\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Заказ #{order_id} не найден")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def run_bot():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан!")
        return
    
    print("=" * 50)
    print("🤖 ЗАПУСК GENSHIN FARM BOT")
    print("=" * 50)
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"🌐 API URL: {FLASK_API_URL}")
    print(f"🔑 Токен бота: {BOT_TOKEN[:20]}...")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # КРИТИЧЕСКИ ВАЖНО: удаляем старый вебхук
    try:
        await app.bot.delete_webhook()
        print("✅ Старый вебхук удален")
    except Exception as e:
        print(f"⚠️ Ошибка удаления вебхука: {e}")
    
    print("✅ БОТ ЗАПУЩЕН! Ожидание сообщений...")
    await app.run_polling()

def start_bot_thread():
    asyncio.run(run_bot())

if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=start_bot_thread)
    bot_thread.start()
    
    # Запускаем фейковый веб-сервер для Render
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Запуск веб-сервера для Render на порту {port}")
    app_web.run(host='0.0.0.0', port=port)
