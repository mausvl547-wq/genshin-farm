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