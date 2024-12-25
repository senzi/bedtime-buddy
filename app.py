from flask import Flask, render_template, request, jsonify, g
import sqlite3
from datetime import datetime, timedelta
import json

app = Flask(__name__)

DATABASE = 'bedtime.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                check_date DATE NOT NULL,
                check_time TIME NOT NULL,
                is_early BOOLEAN NOT NULL
            )
        ''')
        db.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/checkin', methods=['POST'])
def checkin():
    data = request.get_json()
    username = data.get('username')
    confirmed = data.get('confirmed', False)
    now = datetime.now()
    
    # 修改判断逻辑：0点及以后算晚睡
    is_early = now.hour < 24 and now.hour >= 12
    
    # 使用服务器时间，12点为界
    check_date = (now - timedelta(hours=12)).strftime('%Y-%m-%d')
    check_time = now.strftime('%H:%M:%S')
    
    db = get_db()
    
    # 检查是否已经打卡
    cur = db.execute(
        'SELECT id, check_time FROM checkins WHERE username = ? AND check_date = ?',
        (username, check_date)
    )
    existing_record = cur.fetchone()
    
    if existing_record and not confirmed:
        # 如果已经有记录且未确认，返回需要确认的信息
        return jsonify({
            'success': True,
            'needsConfirmation': True,
            'previousTime': existing_record['check_time']
        })
    
    if existing_record:
        # 更新现有记录
        db.execute(
            'UPDATE checkins SET check_time = ?, is_early = ? WHERE id = ?',
            (check_time, is_early, existing_record['id'])
        )
        db.commit()
        return jsonify({
            'success': True,
            'message': '打卡时间已更新！'
        })
    
    # 新建打卡记录
    db.execute(
        'INSERT INTO checkins (username, check_date, check_time, is_early) VALUES (?, ?, ?, ?)',
        (username, check_date, check_time, is_early)
    )
    db.commit()
    
    return jsonify({
        'success': True,
        'message': '打卡成功！'
    })

@app.route('/get_all_streaks')
def get_all_streaks():
    db = get_db()
    # 获取所有用户
    cur = db.execute('SELECT DISTINCT username FROM checkins')
    users = [row['username'] for row in cur.fetchall()]
    
    streaks = []
    for username in users:
        # 获取每个用户的连续打卡天数
        cur = db.execute(
            'SELECT check_date, is_early FROM checkins WHERE username = ? ORDER BY check_date DESC',
            (username,)
        )
        records = cur.fetchall()
        
        streak = 0
        today = (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%d')
        
        for record in records:
            if record['check_date'] == today and record['is_early']:
                streak += 1
                today = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                break
                
        streaks.append({
            'username': username,
            'streak': streak
        })
    
    return jsonify(streaks)

@app.route('/get_checkins')
def get_checkins():
    db = get_db()
    cur = db.execute('SELECT * FROM checkins ORDER BY check_date DESC, check_time DESC')
    checkins = [dict(row) for row in cur.fetchall()]
    return jsonify(checkins)

@app.route('/get_streak/<username>')
def get_streak(username):
    db = get_db()
    cur = db.execute(
        'SELECT check_date, is_early FROM checkins WHERE username = ? ORDER BY check_date DESC',
        (username,)
    )
    records = cur.fetchall()
    
    streak = 0
    today = (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%d')
    
    for i, record in enumerate(records):
        if record['check_date'] == today and record['is_early']:
            streak += 1
            today = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            break
            
    return jsonify({'streak': streak})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)