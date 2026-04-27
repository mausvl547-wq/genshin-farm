from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import secrets
import re
import os  # ДОБАВЛЕНО: для работы с переменными окружения

app = Flask(__name__)

# ======================= НАСТРОЙКИ БАЗЫ ДАННЫХ (ДОБАВЛЕНО ДЛЯ RENDER) =======================
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Если на Render - используем PostgreSQL, если локально - SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'genshin-super-secret-key-2025')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ======================= МОДЕЛИ =======================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)  # Почта
    username = db.Column(db.String(80), unique=True, nullable=False)  # Никнейм
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='cher')  # 'cher' or 'admin'
    total_earned = db.Column(db.Float, default=0.0)
    paid_out = db.Column(db.Float, default=0.0)
    balance = db.Column(db.Float, default=0.0)
    telegram_id = db.Column(db.String(100), nullable=True)  # Для уведомлений
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_password(self):
        """Генерирует случайный пароль"""
        password = secrets.token_urlsafe(8)
        self.set_password(password)
        return password

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    reward = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='new')  # new, taken, completed
    taken_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    taken_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь с FunPay (опционально)
    funpay_url = db.Column(db.String(500), nullable=True)
    funpay_order_id = db.Column(db.String(100), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ======================= МАРШРУТЫ =======================
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_panel'))
            return redirect(url_for('dashboard'))
        flash('❌ Неверная почта или пароль')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_panel'))
    
    available_orders = Order.query.filter_by(status='new').all()
    my_orders = Order.query.filter_by(taken_by=current_user.id, status='taken').all()
    completed_orders = Order.query.filter_by(taken_by=current_user.id, status='completed').order_by(Order.completed_at.desc()).limit(10).all()
    
    return render_template('dashboard.html', 
                         available=available_orders, 
                         my_orders=my_orders,
                         completed_orders=completed_orders,
                         user=current_user)

@app.route('/take_order/<int:order_id>')
@login_required
def take_order(order_id):
    order = Order.query.get(order_id)
    if order and order.status == 'new':
        order.status = 'taken'
        order.taken_by = current_user.id
        order.taken_at = datetime.utcnow()
        db.session.commit()
        flash(f'✅ Заказ "{order.title}" взят в работу!')
    else:
        flash('❌ Заказ уже занят!')
    return redirect(url_for('dashboard'))

@app.route('/complete_order/<int:order_id>')
@login_required
def complete_order(order_id):
    order = Order.query.get(order_id)
    if order and order.taken_by == current_user.id and order.status == 'taken':
        order.status = 'completed'
        order.completed_at = datetime.utcnow()
        current_user.total_earned += order.reward
        current_user.balance += order.reward
        db.session.commit()
        flash(f'🎉 Заказ "{order.title}" выполнен! +{order.reward} руб.')
    else:
        flash('❌ Ошибка: вы не можете завершить этот заказ')
    return redirect(url_for('dashboard'))

# ======================= АДМИНКА =======================
@app.route('/admin')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    stats = {
        'total_users': User.query.count(),
        'total_orders': Order.query.count(),
        'completed_orders': Order.query.filter_by(status='completed').count(),
        'total_payout': db.session.query(db.func.sum(User.paid_out)).scalar() or 0
    }
    return render_template('admin.html', users=users, orders=orders, stats=stats)

@app.route('/admin/add_user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        return jsonify({'error': 'Нет прав'}), 403
    
    email = request.form.get('email')
    username = request.form.get('username')
    
    # Проверка на существование
    if User.query.filter_by(email=email).first():
        flash('❌ Пользователь с такой почтой уже существует')
        return redirect(url_for('admin_panel'))
    
    if User.query.filter_by(username=username).first():
        flash('❌ Пользователь с таким именем уже существует')
        return redirect(url_for('admin_panel'))
    
    # Валидация email
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        flash('❌ Некорректный email')
        return redirect(url_for('admin_panel'))
    
    # Создаем пользователя
    new_user = User(email=email, username=username, role='cher')
    generated_password = new_user.generate_password()
    db.session.add(new_user)
    db.session.commit()
    
    flash(f'✅ Пользователь {username} создан! Пароль: {generated_password} (сохраните и передайте пользователю)')
    return redirect(url_for('admin_panel'))

@app.route('/admin/reset_password/<int:user_id>')
@login_required
def reset_password(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    user = User.query.get(user_id)
    if user:
        new_password = user.generate_password()
        db.session.commit()
        flash(f'🔑 Новый пароль для {user.username}: {new_password}')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user/<int:user_id>')
@login_required
def delete_user(user_id):
    if current_user.role != 'admin' or user_id == current_user.id:
        flash('❌ Нельзя удалить себя')
        return redirect(url_for('admin_panel'))
    
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash(f'✅ Пользователь {user.username} удален')
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_order', methods=['POST'])
@login_required
def add_order():
    if current_user.role != 'admin':
        return jsonify({'error': 'Нет прав'}), 403
    
    title = request.form.get('title')
    description = request.form.get('description')
    reward = float(request.form.get('reward', 0))
    
    order = Order(title=title, description=description, reward=reward)
    db.session.add(order)
    db.session.commit()
    flash(f'✅ Заказ "{title}" добавлен')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_order/<int:order_id>')
@login_required
def delete_order(order_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    order = Order.query.get(order_id)
    if order:
        db.session.delete(order)
        db.session.commit()
        flash('✅ Заказ удален')
    return redirect(url_for('admin_panel'))

@app.route('/admin/pay_user/<int:user_id>', methods=['POST'])
@login_required
def pay_user(user_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Нет прав'}), 403
    
    user = User.query.get(user_id)
    amount = float(request.form.get('amount', 0))
    if user and amount > 0 and amount <= user.balance:
        user.balance -= amount
        user.paid_out += amount
        db.session.commit()
        flash(f'💰 Выплачено {user.username}: {amount} руб.')
    else:
        flash('❌ Ошибка выплаты: неверная сумма')
    return redirect(url_for('admin_panel'))

# ======================= API ДЛЯ ТЕЛЕГРАМ БОТА =======================
@app.route('/api/bot/add_order', methods=['POST'])
def api_add_order():
    """Эндпоинт для бота: добавление заказа"""
    try:
        data = request.json
        title = data.get('title')
        description = data.get('description')
        reward = float(data.get('reward', 0))
        funpay_url = data.get('funpay_url', '')
        
        if not title or not description or reward <= 0:
            return jsonify({'error': 'Неверные данные'}), 400
        
        order = Order(
            title=title,
            description=description,
            reward=reward,
            funpay_url=funpay_url
        )
        db.session.add(order)
        db.session.commit()
        
        return jsonify({'success': True, 'order_id': order.id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bot/stats', methods=['GET'])
def api_stats():
    """Статистика для бота"""
    stats = {
        'total_orders': Order.query.count(),
        'completed_orders': Order.query.filter_by(status='completed').count(),
        'total_earned': db.session.query(db.func.sum(User.total_earned)).scalar() or 0
    }
    return jsonify(stats)

# ======================= API ДЛЯ БОТА (НОВЫЕ ФУНКЦИИ) =======================
@app.route('/api/bot/order_info/<int:order_id>', methods=['GET'])
def api_order_info(order_id):
    """Информация о заказе: кто взял, статус"""
    order = Order.query.get(order_id)
    if not order:
        return jsonify({'error': 'Заказ не найден'}), 404
    
    result = {
        'id': order.id,
        'title': order.title,
        'description': order.description,
        'reward': order.reward,
        'status': order.status,
        'funpay_url': order.funpay_url
    }
    
    if order.taken_by:
        user = User.query.get(order.taken_by)
        result['taken_by'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email
        }
        result['taken_at'] = order.taken_at.strftime('%Y-%m-%d %H:%M:%S') if order.taken_at else None
    
    if order.completed_at:
        result['completed_at'] = order.completed_at.strftime('%Y-%m-%d %H:%M:%S')
    
    return jsonify(result)

@app.route('/api/bot/user_stats/<int:user_id>', methods=['GET'])
def api_user_stats(user_id):
    """Статистика пользователя по ID"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    # Заказы пользователя
    taken_orders = Order.query.filter_by(taken_by=user_id, status='taken').count()
    completed_orders = Order.query.filter_by(taken_by=user_id, status='completed').count()
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'total_earned': user.total_earned,
        'balance': user.balance,
        'paid_out': user.paid_out,
        'taken_orders': taken_orders,
        'completed_orders': completed_orders
    })

@app.route('/api/bot/active_orders', methods=['GET'])
def api_active_orders():
    """Все активные заказы (кто взял)"""
    orders = Order.query.filter(Order.status.in_(['new', 'taken'])).all()
    result = []
    
    for order in orders:
        order_data = {
            'id': order.id,
            'title': order.title,
            'reward': order.reward,
            'status': order.status
        }
        
        if order.taken_by:
            user = User.query.get(order.taken_by)
            order_data['taken_by'] = user.username if user else 'Неизвестно'
        
        result.append(order_data)
    
    return jsonify(result)

@app.route('/api/bot/top_chers', methods=['GET'])
def api_top_chers():
    """Топ качеров по заработку"""
    chers = User.query.filter_by(role='cher').order_by(User.total_earned.desc()).limit(10).all()
    result = []
    
    for cher in chers:
        result.append({
            'username': cher.username,
            'total_earned': cher.total_earned,
            'completed_orders': Order.query.filter_by(taken_by=cher.id, status='completed').count()
        })
    
    return jsonify(result)

# ======================= ИНИЦИАЛИЗАЦИЯ =======================
def init_db():
    with app.app_context():
        db.create_all()
        
        # Создаем админа если нет
        admin = User.query.filter_by(email='admin@farm.com').first()
        if not admin:
            admin = User(email='admin@farm.com', username='Администратор', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("[OK] Admin created: admin@farm.com / admin123")
        
        # Создаем тестового качера
        test_cher = User.query.filter_by(email='cher@test.com').first()
        if not test_cher:
            test_cher = User(email='cher@test.com', username='Люмин', role='cher')
            test_cher.set_password('cher123')
            db.session.add(test_cher)
            db.session.commit()
            
            # Добавляем тестовый заказ
            test_order = Order(
                title='🌿 Фарм цветов селезенки x20',
                description='Собрать 20 цветов селезенки в Ли Юэ. Локация: ущелье Миньюнь',
                reward=250.0
            )
            db.session.add(test_order)
            db.session.commit()
            print("[OK] Test user and order created")

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)