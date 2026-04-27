# bot.py - ИСПРАВЛЕННАЯ ВЕРСИЯ (без синтаксических ошибок)
import asyncio
import requests
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ============= ТВОИ ДАННЫЕ =============
BOT_TOKEN = "8789024886:AAEoJN_Z1KqIQyiCgPsPgo6iGNpE-JvixHc"
ADMIN_IDS = [1288498341, 6893022735]

FLASK_API_URL = os.environ.get('FLASK_API_URL', 'http://127.0.0.1:5000/api/bot')
# ====================================

# Глобальное меню
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Активные заказы", callback_data="active_orders")],
        [InlineKeyboardButton("🏆 Топ качеров", callback_data="top_chers")],
        [InlineKeyboardButton("🔍 Поиск заказа по ID", callback_data="search_order")],
        [InlineKeyboardButton("📈 Моя статистика", callback_data="my_stats")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            "🌟 *Genshin Farm Bot - Админ панель*\n\n"
            "📌 *Как добавить заказ:*\n"
            "1. Отправь ссылку на FunPay\n"
            "2. Бот попросит ввести цену\n"
            "3. Затем название\n"
            "4. И описание\n\n"
            "📌 *Другие команды:*\n"
            "• /stats - Общая статистика\n"
            "• Отправь ID заказа - узнать кто взял\n\n"
            "👇 *Используй кнопки ниже:*",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text("❌ У вас нет доступа к этому боту")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Общая статистика"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа!")
        return
    
    try:
        # Получаем данные с сервера
        active_response = requests.get(f"{FLASK_API_URL}/active_orders", timeout=5)
        active_orders = active_response.json() if active_response.status_code == 200 else []
        
        taken_orders = [o for o in active_orders if o['status'] == 'taken']
        new_orders = [o for o in active_orders if o['status'] == 'new']
        
        # Формируем ответ
        message = f"📊 *Общая статистика*\n\n"
        message += f"📋 Всего активных заказов: {len(active_orders)}\n"
        message += f"🆕 Новых заказов: {len(new_orders)}\n"
        message += f"⚡ В работе: {len(taken_orders)}\n\n"
        
        if taken_orders:
            message += "*Кто что взял:*\n"
            for order in taken_orders[:10]:
                message += f"• Заказ #{order['id']} - {order['title'][:30]}...\n"
                message += f"  👤 Взял: {order.get('taken_by', 'Неизвестно')}\n"
                message += f"  💰 {order['reward']}₽\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_funpay_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылки - запрашиваем цену"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Нет доступа!")
        return
    
    url = update.message.text.strip()
    
    if "funpay.com" not in url:
        # Проверяем, может это ID заказа?
        if url.isdigit():
            await check_order_by_id(update, int(url))
            return
        else:
            await update.message.reply_text("❌ Отправь ссылку на FunPay или ID заказа")
            return
    
    # Сохраняем URL и запрашиваем цену
    context.user_data['pending_order_url'] = url
    await update.message.reply_text(
        "📝 *Создание нового заказа*\n\n"
        "📍 Ссылка получена!\n\n"
        "💰 *Шаг 1 из 3:* Введи цену заказа (в рублях)\n\n"
        "Примеры: `250` или `150.50` или `1000`",
        parse_mode='Markdown'
    )
    context.user_data['awaiting_price'] = True

async def handle_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода цены - запрашиваем название"""
    if context.user_data.get('awaiting_price'):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Нет доступа!")
            return
        
        try:
            price = float(update.message.text.replace(',', '.'))
            
            if price <= 0:
                await update.message.reply_text("❌ Цена должна быть больше 0\n\nВведи цену еще раз:")
                return
            
            # Сохраняем цену и запрашиваем название
            context.user_data['order_price'] = price
            context.user_data['awaiting_price'] = False
            context.user_data['awaiting_title'] = True
            
            await update.message.reply_text(
                f"✅ Цена сохранена: *{price}₽*\n\n"
                f"📋 *Шаг 2 из 3:* Введи название заказа\n\n"
                f"Примеры:\n"
                f"• `Фарм руды для возвышения`\n"
                f"• `Сбор скарабеев x10`\n"
                f"• `Прохождение данжа`",
                parse_mode='Markdown'
            )
            
        except ValueError:
            await update.message.reply_text("❌ Ошибка! Введи число (например: 250)\n\nПопробуй еще раз:")

async def handle_title_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода названия - запрашиваем описание"""
    if context.user_data.get('awaiting_title'):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Нет доступа!")
            return
        
        title = update.message.text.strip()
        
        if len(title) < 3:
            await update.message.reply_text("❌ Название слишком короткое (минимум 3 символа)\n\nВведи название еще раз:")
            return
        
        # Сохраняем название и запрашиваем описание
        context.user_data['order_title'] = title
        context.user_data['awaiting_title'] = False
        context.user_data['awaiting_description'] = True
        
        await update.message.reply_text(
            f"✅ Название сохранено: *{title}*\n\n"
            f"📝 *Шаг 3 из 3:* Введи описание заказа\n\n"
            f"Что нужно сделать? Какие ресурсы фармить?\n\n"
            f"Пример:\n"
            f"`Собрать 30 цветов селезенки в Ли Юэ. Локация: ущелье Миньюнь.`",
            parse_mode='Markdown'
        )

async def handle_description_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода описания - создаем заказ"""
    if context.user_data.get('awaiting_description'):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Нет доступа!")
            return
        
        description = update.message.text.strip()
        title = context.user_data.get('order_title')
        price = context.user_data.get('order_price')
        url = context.user_data.get('pending_order_url')
        
        if len(description) < 5:
            await update.message.reply_text("❌ Описание слишком короткое (минимум 5 символов)\n\nВведи описание еще раз:")
            return
        
        # Формируем полное описание с ссылкой
        full_description = f"{description}\n\n🔗 Ссылка на FunPay: {url}"
        
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
                    f"📝 *Описание:* {description[:150]}...\n\n"
                    f"🆔 *ID заказа:* {data.get('order_id')}\n\n"
                    f"💡 Теперь качеры могут взять его в работу!",
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard()
                )
            else:
                await update.message.reply_text(f"❌ Ошибка при создании: {response.text}")
        except requests.exceptions.ConnectionError:
            await update.message.reply_text(
                "❌ Ошибка подключения к серверу!\n\n"
                "Убедись что Flask запущен: `python app.py`",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        
        # Очищаем данные пользователя
        context.user_data.clear()

async def check_order_by_id(update: Update, order_id):
    """Проверка заказа по ID"""
    try:
        response = requests.get(f"{FLASK_API_URL}/order_info/{order_id}", timeout=5)
        
        if response.status_code == 200:
            order = response.json()
            
            status_emoji = {
                'new': '🆕',
                'taken': '⚡',
                'completed': '✅'
            }.get(order['status'], '❓')
            
            status_text = {
                'new': 'Новый (ждет исполнителя)',
                'taken': 'В работе',
                'completed': 'Выполнен'
            }.get(order['status'], order['status'])
            
            message = f"{status_emoji} *Заказ #{order['id']}*\n\n"
            message += f"📋 *Название:* {order['title']}\n"
            message += f"💰 *Цена:* {order['reward']}₽\n"
            message += f"📊 *Статус:* {status_text}\n"
            message += f"📝 *Описание:* {order['description'][:200]}...\n"
            
            if order.get('taken_by'):
                message += f"\n👤 *Взял:* {order['taken_by']['username']}\n"
                message += f"📧 *Email:* {order['taken_by']['email']}\n"
                if order.get('taken_at'):
                    message += f"⏰ *Время:* {order['taken_at']}\n"
            
            if order.get('completed_at'):
                message += f"✅ *Завершен:* {order['completed_at']}\n"
            
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
                message += "🆕 *Новые (ждут исполнителя):*\n"
                for order in new_orders[:5]:
                    message += f"• #{order['id']} - {order['title'][:35]}... - {order['reward']}₽\n"
                message += "\n"
            
            if taken_orders:
                message += "⚡ *В работе:*\n"
                for order in taken_orders[:5]:
                    taken_by = order.get('taken_by', 'Неизвестно')
                    message += f"• #{order['id']} - {order['title'][:30]}...\n"
                    message += f"  👤 Исполнитель: {taken_by}\n"
                    message += f"  💰 {order['reward']}₽\n\n"
            
            message += "💡 *Инструкция:*\n"
            message += "Отправь ID заказа (например 5), чтобы узнать подробности"
            
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())
        else:
            await query.edit_message_text("❌ Ошибка получения данных", reply_markup=get_main_keyboard())
            
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}", reply_markup=get_main_keyboard())

async def top_chers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ качеров"""
    query = update.callback_query
    await query.answer()
    
    try:
        response = requests.get(f"{FLASK_API_URL}/top_chers", timeout=5)
        
        if response.status_code == 200:
            chers = response.json()
            
            if not chers:
                await query.edit_message_text("📭 Нет качеров", reply_markup=get_main_keyboard())
                return
            
            message = "🏆 *Топ качеров по заработку*\n\n"
            
            for i, cher in enumerate(chers[:10], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                message += f"{medal} *{cher['username']}*\n"
                message += f"   💰 Заработано: {cher['total_earned']}₽\n"
                message += f"   📦 Завершено: {cher['completed_orders']} заказов\n\n"
            
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())
        else:
            await query.edit_message_text("❌ Ошибка получения данных", reply_markup=get_main_keyboard())
            
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}", reply_markup=get_main_keyboard())

async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Моя статистика"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        message = "👑 *Админ-панель*\n\n"
        message += "📊 *Доступные действия:*\n"
        message += "• Отправь ссылку на FunPay - создать новый заказ\n"
        message += "• Отправь ID заказа - узнать кто взял\n"
        message += "• /stats - общая статистика\n\n"
        message += "💡 *Совет:* используй кнопки меню для быстрого доступа"
        
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())
    else:
        # Для обычных пользователей - их статистика
        try:
            response = requests.get(f"{FLASK_API_URL}/user_stats/{user_id}", timeout=5)
            
            if response.status_code == 200:
                user = response.json()
                message = f"📈 *Твоя статистика*\n\n"
                message += f"👤 *Имя:* {user['username']}\n"
                message += f"📧 *Email:* {user['email']}\n\n"
                message += f"💰 *Всего заработано:* {user['total_earned']}₽\n"
                message += f"💸 *К выплате:* {user['balance']}₽\n"
                message += f"✅ *Выплачено:* {user['paid_out']}₽\n\n"
                message += f"📦 *Заказов в работе:* {user['taken_orders']}\n"
                message += f"✅ *Выполнено заказов:* {user['completed_orders']}"
                
                await query.edit_message_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())
            else:
                await query.edit_message_text("❌ Не удалось получить статистику", reply_markup=get_main_keyboard())
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {str(e)}", reply_markup=get_main_keyboard())

async def search_order_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос ID заказа"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔍 *Поиск заказа*\n\n"
        "Введи ID заказа (например 5):\n\n"
        "💡 ID заказа можно увидеть при его создании",
        parse_mode='Markdown'
    )
    context.user_data['awaiting_order_id'] = True

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото"""
    await update.message.reply_text(
        "📸 Скриншот получен!\n\n"
        "Отправь ссылку на FunPay, чтобы создать заказ"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик текстовых сообщений"""
    # Проверяем на каком мы этапе создания заказа
    if context.user_data.get('awaiting_price'):
        await handle_price_input(update, context)
    elif context.user_data.get('awaiting_title'):
        await handle_title_input(update, context)
    elif context.user_data.get('awaiting_description'):
        await handle_description_input(update, context)
    elif context.user_data.get('awaiting_order_id'):
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Нет доступа!")
            return
        
        text = update.message.text
        if text.isdigit():
            await check_order_by_id(update, int(text))
        else:
            await update.message.reply_text("❌ Введи число (ID заказа)")
        
        context.user_data['awaiting_order_id'] = False
    else:
        # Если не в процессе создания - обрабатываем как ссылку или ID
        await handle_funpay_link(update, context)

async def main():
    print("=" * 50)
    print("🤖 ЗАПУСК GENSHIN FARM BOT")
    print("=" * 50)
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"🌐 API URL: {FLASK_API_URL}")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    
    # Callback кнопки
    app.add_handler(CallbackQueryHandler(active_orders, pattern="active_orders"))
    app.add_handler(CallbackQueryHandler(top_chers, pattern="top_chers"))
    app.add_handler(CallbackQueryHandler(search_order_prompt, pattern="search_order"))
    app.add_handler(CallbackQueryHandler(my_stats, pattern="my_stats"))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("✅ БОТ УСПЕШНО ЗАПУЩЕН!")
    print("📌 Доступные функции:")
    print("   • /start - Главное меню")
    print("   • /stats - Общая статистика")
    print("   • Отправь ссылку FunPay - создать заказ (пошагово)")
    print("   • Отправь ID заказа - узнать кто взял")
    print("=" * 50)
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == '__main__':
    asyncio.run(main())