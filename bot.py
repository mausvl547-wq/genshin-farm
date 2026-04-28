# bot.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
import os
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8789024886:AAFLq4oyepyba8qa0l-URnXQ6gRSWl1kDYc"
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
            "📌 *Команды:*\n"
            "/start - Главное меню\n"
            "/new - Новый заказ\n"
            "/cancel - Отмена\n\n"
            "👇 *Кнопки:*",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text("❌ Нет доступа")

async def new_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    
    context.user_data.clear()
    context.user_data['step'] = 'title'
    await update.message.reply_text(
        "📝 *Новый заказ*\n\n"
        "**Шаг 1/4:** Введи *название*\n\n"
        "Пример: `Фарм скарабеев x10`\n\n"
        "Отмена: /cancel",
        parse_mode='Markdown'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    
    context.user_data.clear()
    await update.message.reply_text("❌ Отменено", reply_markup=get_main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    
    step = context.user_data.get('step')
    text = update.message.text.strip()
    
    if not step:
        if text.isdigit():
            await check_order(update, int(text))
        else:
            await update.message.reply_text("❌ Отправь ID заказа или /new", reply_markup=get_main_keyboard())
        return
    
    if step == 'title':
        context.user_data['title'] = text
        context.user_data['step'] = 'price'
        await update.message.reply_text(
            f"✅ Название: {text}\n\n"
            "**Шаг 2/4:** Введи *цену* (₽)\n"
            "Пример: `250`",
            parse_mode='Markdown'
        )
    elif step == 'price':
        try:
            price = float(text.replace(',', '.'))
            context.user_data['price'] = price
            context.user_data['step'] = 'desc'
            await update.message.reply_text(
                f"✅ Цена: {price}₽\n\n"
                "**Шаг 3/4:** Введи *описание*\n"
                "Пример: `Собрать 10 скарабеев в пустыне`",
                parse_mode='Markdown'
            )
        except:
            await update.message.reply_text("❌ Ошибка: введи число")
    elif step == 'desc':
        context.user_data['desc'] = text
        context.user_data['step'] = 'url'
        await update.message.reply_text(
            "**Шаг 4/4:** Отправь *ссылку FunPay* (или /skip)",
            parse_mode='Markdown'
        )
    elif step == 'url':
        url = text if "funpay.com" in text else ''
        await save_order(update, context, url)

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа")
        return
    await save_order(update, context, '')

async def save_order(update, context, url):
    title = context.user_data.get('title')
    price = context.user_data.get('price')
    desc = context.user_data.get('desc')
    
    if not all([title, price, desc]):
        await update.message.reply_text("❌ Ошибка: начни заново с /new")
        context.user_data.clear()
        return
    
    full_desc = desc
    if url:
        full_desc += f"\n\n🔗 {url}"
    
    try:
        r = requests.post(f"{FLASK_API_URL}/add_order", json={
            'title': title,
            'description': full_desc,
            'reward': price,
            'funpay_url': url
        }, timeout=10)
        if r.status_code == 200:
            data = r.json()
            await update.message.reply_text(
                f"✅ *Заказ #{data['order_id']} создан!*\n"
                f"📋 {title}\n💰 {price}₽",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text("❌ Ошибка API")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    
    context.user_data.clear()

async def check_order(update, order_id):
    try:
        r = requests.get(f"{FLASK_API_URL}/order_info/{order_id}", timeout=5)
        if r.status_code == 200:
            o = r.json()
            msg = f"📦 *Заказ #{o['id']}*\n📋 {o['title']}\n💰 {o['reward']}₽\n📊 {o['status']}"
            if o.get('taken_by'):
                msg += f"\n👤 Взял: {o['taken_by']['username']}"
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Не найден")
    except:
        await update.message.reply_text("❌ Ошибка")

async def active_orders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        r = requests.get(f"{FLASK_API_URL}/active_orders", timeout=5)
        if r.status_code == 200:
            orders = r.json()
            if not orders:
                await query.edit_message_text("📭 Нет заказов", reply_markup=get_main_keyboard())
                return
            msg = "📊 *Активные заказы*\n\n"
            for o in orders[:10]:
                msg += f"• #{o['id']} - {o['title'][:30]} - {o['reward']}₽\n"
            await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=get_main_keyboard())
        else:
            await query.edit_message_text("❌ Ошибка", reply_markup=get_main_keyboard())
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}", reply_markup=get_main_keyboard())

async def search_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔍 Введи ID заказа:")
    context.user_data['searching'] = True

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('searching'):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            return
        if update.message.text.isdigit():
            await check_order(update, int(update.message.text))
        else:
            await update.message.reply_text("❌ Введи число")
        context.user_data['searching'] = False

async def create_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await new_order(update, context)

# ============= ЗАПУСК =============
def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app_web.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    from threading import Thread
    Thread(target=run_flask).start()
    
    print("🤖 ЗАПУСК БОТА")
    print("=" * 40)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_order))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("skip", skip))
    
    # Callback кнопки
    app.add_handler(CallbackQueryHandler(active_orders_callback, pattern="active_orders"))
    app.add_handler(CallbackQueryHandler(search_prompt, pattern="search_order"))
    app.add_handler(CallbackQueryHandler(create_order_callback, pattern="create_order"))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"🌐 API: {FLASK_API_URL}")
    print("✅ БОТ ЗАПУЩЕН! Ожидание сообщений...")
    
    # Запускаем бота
    app.run_polling(allowed_updates=Update.ALL_TYPES)
