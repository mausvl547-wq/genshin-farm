import asyncio
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ТВОЙ ТОКЕН ОТ BOTFATHER
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# API Flask (админка бота будет отправлять заказы на веб-сервер)
FLASK_API_URL = "http://127.0.0.1:5000/api/bot/add_order"
ADMIN_IDS = [123456789]  # ID Telegram админов, кто может добавлять заказы

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие"""
    await update.message.reply_text(
        "🌟 *Genshin Farm Bot* 🌟\n\n"
        "Я помогаю синхронизировать заказы с FunPay!\n\n"
        "📌 *Как добавить заказ:*\n"
        "1. Отправь ссылку на заказ с FunPay\n"
        "2. Или отправь скриншот заказа\n"
        "3. Бот распарсит и добавит в базу\n\n"
        "⚡ *Доступные команды:*\n"
        "/start - Показать это сообщение",
        parse_mode='Markdown'
    )

async def handle_funpay_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылок на FunPay"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа! Только админы могут добавлять заказы.")
        return
    
    url = update.message.text.strip()
    
    if "funpay.com" not in url:
        await update.message.reply_text("❌ Это не похоже на ссылку с FunPay")
        return
    
    await update.message.reply_text("🔄 Парсинг заказа с FunPay...")
    
    # Реальный парсинг FunPay (нужны куки!)
    try:
        # Тут нужно добавить свои куки от аккаунта FunPay
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Cookie': 'YOUR_FUNPAY_COOKIE_HERE'  # Замени на реальные куки
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Пример парсинга (нужно адаптировать под структуру FunPay)
        title_elem = soup.find('div', class_='tc-item__title')
        price_elem = soup.find('span', class_='tc-price')
        desc_elem = soup.find('div', class_='tc-desc')
        
        # Демо-данные для примера
        title = title_elem.text.strip() if title_elem else "Заказ с FunPay"
        reward = float(price_elem.text.replace('₽', '').strip()) if price_elem else 100.0
        description = desc_elem.text.strip() if desc_elem else "Описание заказа"
        
        # Отправляем на Flask API
        order_data = {
            'title': title,
            'description': description,
            'reward': reward,
            'funpay_url': url
        }
        
        response = requests.post(FLASK_API_URL, json=order_data)
        
        if response.status_code == 200:
            await update.message.reply_text(
                f"✅ *Заказ добавлен в систему!*\n\n"
                f"📋 *Название:* {title}\n"
                f"💰 *Цена:* {reward}₽\n"
                f"📝 *Описание:* {description[:100]}...",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ Ошибка добавления: {response.text}")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка парсинга: {str(e)}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка скриншотов (ручной ввод)"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа!")
        return
    
    await update.message.reply_text("📸 Скриншот получен! Введите данные заказа в формате:\n\n`Название | Цена | Описание`\n\nПример:\nФарм руды | 150 | Собрать 200 кристаллов", parse_mode='Markdown')
    context.user_data['awaiting_order_data'] = True

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ручного ввода заказа"""
    if context.user_data.get('awaiting_order_data'):
        text = update.message.text
        try:
            parts = text.split('|')
            title = parts[0].strip()
            reward = float(parts[1].strip())
            description = parts[2].strip()
            
            order_data = {
                'title': title,
                'description': description,
                'reward': reward
            }
            
            response = requests.post(FLASK_API_URL, json=order_data)
            
            if response.status_code == 200:
                await update.message.reply_text(f"✅ Заказ «{title}» добавлен!")
            else:
                await update.message.reply_text(f"❌ Ошибка: {response.text}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка формата. Используйте: Название | Цена | Описание")
        
        context.user_data['awaiting_order_data'] = False

def main():
    """Запуск бота"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_funpay_link))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    print("🤖 Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()