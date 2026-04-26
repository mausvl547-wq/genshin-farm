# AGENTS.md

## Project Overview
Flask web application (genshin_farm) - task/order management system with Telegram bot integration.

## Dependencies
```
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.2
python-telegram-bot==20.7
requests==2.31.0
beautifulsoup4==4.12.2
werkzeug==3.0.1
```

## Running the App
```bash
pip install -r requirements.txt
python app.py
```
Server runs on http://localhost:5000

## Default Credentials
- Admin: admin@farm.com / admin123
- Cher (test user): cher@test.com / cher123

## Known Issues / Missing Files
- **No Telegram bot integration** - `bot.py` needs valid BOT_TOKEN and FunPay cookies configured

## Database Models
- **User**: id, email, username, password_hash, role (cher/admin), total_earned, balance, telegram_id
- **Order**: id, title, description, reward, status (new/taken/completed), taken_by, funpay_url

## Key Routes
- `/login` - authentication
- `/dashboard` - cher view (available orders, my orders)
- `/admin` - admin panel (manage users, orders, payouts)