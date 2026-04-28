# bot.py - ГОТОВАЯ РАБОЧАЯ ВЕРСИЯ
import os
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============= НОВЫЙ ТОКЕН =============
BOT_TOKEN = "8789024886:AAFLq4oyepyba8qa0l-URnXQ6gRSWl1kDYc"
ADMIN_IDS = [1288498341, 6893022735]
FLASK_API_URL = "https://genshin-farm.onrender.com/api/bot"
# =====================================

app_web = Flask(__name__)

@app_web.route('/')
def health():
    return "Bot is running", 200

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Создать заказ", callback_data="create_order")],
        [InlineKeyboardButton("📊 Активные заказы", callback_data="active_orders")],
        [InlineKeyboardButton("🔍 Поиск заказа", callback_data="search_order")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            "🌟 *Genshin Farm Bot*\n\n"
            "📌 *Команды:*\n"
            "/new - Создать заказ\n"
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
    
    if update.callback_query:
        msg = update.callback_query.message
        await update.callback_query.answer()
    else:
        msg = update.message
    
    context.user_data.clear()
    context.user_data['step'] = 'title'
    await msg.reply_text(
        "📝 *Новый заказ*\n\n"
        "**Шаг 1/4:** Введи *название*\n\n"
        "Пример: `Фарм скарабеев x10`\n"
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
        elif "funpay.com" in text:
            context.user_data['funpay_url'] = text
            context.user_data['step'] = 'title'
            await update.message.reply_text(
                "📝 *Новый заказ*\n\n"
                "📍 Ссылка сохранена!\n"
                "**Шаг 1/4:** Введи *название*",
                parse_mode='Markdown'
            )
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
                "Пример: `Собрать 10 скарабеев`",
                parse_mode='Markdown'
            )
        except:
            await update.message.reply_text("❌ Введи число")
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
    funpay_url = url or context.user_data.get('funpay_url', '')
    
    if not all([title, price, desc]):
        await update.message.reply_text("❌ Ошибка. Начни заново: /new")
        context.user_data.clear()
        return
    
    full_desc = desc
    if funpay_url:
        full_desc += f"\n\n🔗 {funpay_url}"
    
    try:
        r = requests.post(f"{FLASK_API_URL}/add_order", json={
            'title': title,
            'description': full_desc,
            'reward': price,
            'funpay_url': funpay_url
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
    except:
        await query.edit_message_text("❌ Ошибка", reply_markup=get_main_keyboard())

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

# ============= ЗАПУСК =============
if __name__ == '__main__':
    from threading import Thread
    
    def run_flask():
        port = int(os.environ.get('PORT', 10000))
        app_web.run(host='0.0.0.0', port=port)
    
    Thread(target=run_flask).start()
    
    print("=" * 50)
    print("🤖 ЗАПУСК GENSHIN FARM BOT")
    print("=" * 50)
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"🌐 API URL: {FLASK_API_URL}")
    print(f"🔑 Токен: {BOT_TOKEN[:20]}...")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_order))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CallbackQueryHandler(active_orders_callback, pattern="active_orders"))
    app.add_handler(CallbackQueryHandler(search_prompt, pattern="search_order"))
    app.add_handler(CallbackQueryHandler(new_order, pattern="create_order"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    
    print("✅ БОТ ЗАПУЩЕН! Ожидание сообщений...")
    print("=" * 50)
    
    app.run_polling()
