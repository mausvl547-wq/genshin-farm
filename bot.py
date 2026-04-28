# bot.py - ПОЛНАЯ ВЕРСИЯ С РУЧНЫМ ВВОДОМ ДАННЫХ
import os
import requests
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = "8789024886:AAEoJN_Z1KqIQyiCgPsPgo6iGNpE-JvixHc"
ADMIN_IDS = [1288498341, 6893022735]
FLASK_API_URL = "https://genshin-farm.onrender.com/api/bot"

app_web = Flask(__name__)

@app_web.route('/')
def health():
    return "Bot is running", 200

# ============= КЛАВИАТУРЫ =============
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Создать заказ", callback_data="create_order")],
        [InlineKeyboardButton("📊 Активные заказы", callback_data="active_orders")],
        [InlineKeyboardButton("🔍 Поиск заказа", callback_data="search_order")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ============= ОБРАБОТЧИКИ =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            "🌟 *Genshin Farm Bot*\n\n"
            "📌 *Доступные команды:*\n"
            "• /start - Главное меню\n"
            "• /new - Создать новый заказ\n"
            "• Отправь ID заказа - узнать кто взял\n\n"
            "👇 *Используй кнопки ниже:*",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text("❌ Нет доступа")

async def new_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать создание нового заказа"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    
    context.user_data['order_step'] = 'title'
    await update.message.reply_text(
        "📝 *Создание нового заказа*\n\n"
        "**Шаг 1 из 4:** Введи *название* заказа\n\n"
        "Пример: `Фарм скарабеев x10`",
        parse_mode='Markdown'
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    
    step = context.user_data.get('order_step')
    text = update.message.text.strip()
    
    # Если не в режиме создания заказа - проверяем ID
    if not step:
        if text.isdigit():
            await check_order_by_id(update, int(text))
        elif "funpay.com" in text:
            # Если отправлена ссылка, начинаем создание заказа
            context.user_data['funpay_url'] = text
            context.user_data['order_step'] = 'title'
            await update.message.reply_text(
                "📝 *Создание нового заказа*\n\n"
                "📍 Ссылка сохранена!\n\n"
                "**Шаг 1 из 4:** Введи *название* заказа",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "❌ Отправь ID заказа (цифру) или нажми кнопку 'Создать заказ'",
                reply_markup=get_main_keyboard()
            )
        return
    
    # Режим создания заказа
    if step == 'title':
        context.user_data['order_title'] = text
        context.user_data['order_step'] = 'price'
        await update.message.reply_text(
            f"✅ Название: *{text}*\n\n"
            "**Шаг 2 из 4:** Введи *цену* заказа (в рублях)\n\n"
            "Пример: `250` или `150.50`",
            parse_mode='Markdown'
        )
    
    elif step == 'price':
        try:
            price = float(text.replace(',', '.'))
            if price <= 0:
                await update.message.reply_text("❌ Цена должна быть больше 0. Попробуй еще раз:")
                return
            context.user_data['order_price'] = price
            context.user_data['order_step'] = 'description'
            await update.message.reply_text(
                f"✅ Цена: *{price}₽*\n\n"
                "**Шаг 3 из 4:** Введи *описание* заказа\n\n"
                "Что нужно сделать? Какие ресурсы фармить?\n\n"
                "Пример: `Собрать 10 скарабеев в пустыне Сумеру. Старт от пирамиды.`",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Введи число (например: 250). Попробуй еще раз:")
    
    elif step == 'description':
        context.user_data['order_description'] = text
        context.user_data['order_step'] = 'url'
        await update.message.reply_text(
            f"✅ Описание сохранено\n\n"
            "**Шаг 4 из 4:** Отправь *ссылку на FunPay* (или нажми /skip если нет ссылки)\n\n"
            "Пример: `https://funpay.com/orders/12345`",
            parse_mode='Markdown'
        )
    
    elif step == 'url':
        funpay_url = text if "funpay.com" in text else context.user_data.get('funpay_url', '')
        await create_final_order(update, context, funpay_url)

async def skip_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропустить добавление ссылки"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    
    await create_final_order(update, context, '')

async def create_final_order(update: Update, context: ContextTypes.DEFAULT_TYPE, funpay_url: str):
    """Создание заказа в базе данных"""
    title = context.user_data.get('order_title')
    price = context.user_data.get('order_price')
    description = context.user_data.get('order_description')
    url = funpay_url or context.user_data.get('funpay_url', '')
    
    if not all([title, price, description]):
        await update.message.reply_text("❌ Ошибка: не все данные заполнены. Начни заново с /new")
        context.user_data.clear()
        return
    
    # Добавляем ссылку в описание если есть
    full_description = description
    if url:
        full_description += f"\n\n🔗 Ссылка: {url}"
    
    order_data = {
        'title': title,
        'description': full_description,
        'reward': price,
        'funpay_url': url
    }
    
    await update.message.reply_text("🔄 Создаю заказ...")
    
    try:
        response = requests.post(f"{FLASK_API_URL}/add_order", json=order_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            await update.message.reply_text(
                f"✅ *Заказ успешно создан!*\n\n"
                f"📋 *Название:* {title}\n"
                f"💰 *Цена:* {price}₽\n"
                f"📝 *Описание:* {description[:100]}...\n\n"
                f"🆔 *ID заказа:* `{data.get('order_id')}`\n\n"
                f"💡 Теперь качеры могут взять его в работу!",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text(f"❌ Ошибка API: {response.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    # Очищаем данные
    context.user_data.clear()

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания заказа"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Создание заказа отменено",
        reply_markup=get_main_keyboard()
    )

async def check_order_by_id(update: Update, order_id: int):
    """Проверка заказа по ID"""
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
            message += f"📝 *Описание:* {order['description'][:200]}...\n"
            
            if order.get('taken_by'):
                message += f"\n👤 *Взял:* {order['taken_by']['username']}\n"
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(f"❌ Заказ #{order_id} не найден", reply_markup=get_main_keyboard())
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def active_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные заказы"""
    query = update.callback_query
    await query.answer()
    
    try:
        response = requests.get(f"{FLASK_API_URL}/active_orders", timeout=5)
        
        if response.status_code == 200:
            orders = response.json()
            
            if not orders:
                await query.edit_message_text("📭 Нет активных заказов", reply_markup=get_main_keyboard())
                return
            
            message = "📊 *Активные заказы*\n\n"
            
            new_orders = [o for o in orders if o['status'] == 'new']
            taken_orders = [o for o in orders if o['status'] == 'taken']
            
            if new_orders:
                message += "🆕 *Новые:*\n"
                for order in new_orders[:5]:
                    message += f"• #{order['id']} - {order['title'][:35]}... - {order['reward']}₽\n"
                message += "\n"
            
            if taken_orders:
                message += "⚡ *В работе:*\n"
                for order in taken_orders[:5]:
                    taken_by = order.get('taken_by', 'Неизвестно')
                    message += f"• #{order['id']} - {order['title'][:30]}... - {order['reward']}₽ 👤 {taken_by}\n"
                message += "\n"
            
            message += "💡 Отправь ID заказа (цифру) для подробностей"
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())
        else:
            await query.edit_message_text("❌ Ошибка", reply_markup=get_main_keyboard())
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}", reply_markup=get_main_keyboard())

async def search_order_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос ID заказа"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔍 *Поиск заказа*\n\n"
        "Введи ID заказа (например 5):",
        parse_mode='Markdown'
    )
    context.user_data['awaiting_order_id'] = True

async def handle_search_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода ID для поиска"""
    if context.user_data.get('awaiting_order_id'):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Нет доступа")
            return
        
        text = update.message.text
        if text.isdigit():
            await check_order_by_id(update, int(text))
        else:
            await update.message.reply_text("❌ Введи число (ID заказа)", reply_markup=get_main_keyboard())
        
        context.user_data['awaiting_order_id'] = False

# ============= ЗАПУСК =============
if __name__ == '__main__':
    from threading import Thread
    
    def run_flask():
        port = int(os.environ.get('PORT', 10000))
        app_web.run(host='0.0.0.0', port=port)
    
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    print("=" * 50)
    print("🤖 ЗАПУСК GENSHIN FARM BOT")
    print("=" * 50)
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"🌐 API URL: {FLASK_API_URL}")
    print("=" * 50)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def setup_and_run():
        app = Application.builder().token(BOT_TOKEN).build()
        
        await app.bot.delete_webhook(drop_pending_updates=True)
        await app.bot.log_out()
        print("✅ Вебхук удалён и сессии завершены")
        
        # Команды
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("new", new_order))
        app.add_handler(CommandHandler("skip", skip_url))
        app.add_handler(CommandHandler("cancel", cancel_order))
        
        # Callback кнопки
        app.add_handler(CallbackQueryHandler(active_orders, pattern="active_orders"))
        app.add_handler(CallbackQueryHandler(search_order_prompt, pattern="search_order"))
        app.add_handler(CallbackQueryHandler(new_order, pattern="create_order"))
        
        # Обработчики текста
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_text))
        
        print("✅ БОТ ЗАПУЩЕН! Ожидание сообщений...")
        await app.run_polling()
    
    try:
        loop.run_until_complete(setup_and_run())
    except KeyboardInterrupt:
        print("🛑 Бот остановлен")
