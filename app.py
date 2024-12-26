from flask import Flask, render_template, request, jsonify, g
import sqlite3
from datetime import datetime, timedelta
import json
from collections import defaultdict

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
        
        # 添加用户名映射表
        db.execute('''
            CREATE TABLE IF NOT EXISTS user_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                display_name TEXT NOT NULL,
                username TEXT NOT NULL
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
    
    # 获取所有显示名称
    display_names = db.execute('''
        SELECT DISTINCT display_name FROM user_mappings
        UNION
        SELECT DISTINCT username FROM checkins 
        WHERE username NOT IN (
            SELECT username FROM user_mappings
        )
    ''').fetchall()
    
    # 计算每个用户的连续天数
    streaks = []
    for (display_name,) in display_names:
        streak = calculate_streak(db, display_name)
        streaks.append({
            'username': display_name,
            'streak': streak
        })
    
    # 按连续天数降序排序
    streaks.sort(key=lambda x: x['streak'], reverse=True)
    return jsonify(streaks)

@app.route('/get_checkins')
def get_checkins():
    db = get_db()
    
    # 首先获取所有用户名映射
    mappings = {}
    mapping_rows = db.execute('SELECT username, display_name FROM user_mappings').fetchall()
    for username, display_name in mapping_rows:
        mappings[username] = display_name

    # 获取所有打卡记录
    checkins = db.execute('''
        SELECT username, check_date, check_time, is_early
        FROM checkins
        ORDER BY check_date DESC, check_time DESC
    ''').fetchall()
    
    # 用于存储每个用户每天的最新记录
    latest_records = {}  # 格式: {(display_name, date): record}
    
    for row in checkins:
        username, check_date, check_time, is_early = row
        # 获取映射后的用户名
        display_name = mappings.get(username, username)
        
        # 使用(显示名称, 日期)作为键
        key = (display_name, check_date)
        
        # 只保存每个用户每天的第一条记录（因为记录已经按时间倒序排序）
        if key not in latest_records:
            latest_records[key] = {
                'username': display_name,
                'check_date': check_date,
                'check_time': check_time,
                'is_early': bool(is_early)
            }
    
    # 将字典转换为列表并按日期和时间排序
    result = list(latest_records.values())
    result.sort(key=lambda x: (x['check_date'], x['check_time']), reverse=True)
    
    return jsonify(result)

def calculate_streak(db, username):
    """计算指定用户的连续早睡天数"""
    # 获取所有映射到这个显示名称的用户名
    usernames = db.execute('''
        SELECT username FROM user_mappings 
        WHERE display_name = ? 
        UNION 
        SELECT ? WHERE NOT EXISTS (
            SELECT 1 FROM user_mappings WHERE display_name = ?
        )
    ''', (username, username, username)).fetchall()
    usernames = [row[0] for row in usernames]
    
    # 使用所有可能的用户名查询打卡记录
    placeholders = ','.join(['?' for _ in usernames])
    query = f'''
        SELECT username, check_date, check_time, is_early
        FROM checkins
        WHERE username IN ({placeholders})
        ORDER BY check_date DESC, check_time DESC
    '''
    
    checkins = db.execute(query, usernames).fetchall()
    
    # 用字典记录每天最新的打卡记录
    daily_records = {}  # 格式: {date: is_early}
    for username, check_date, check_time, is_early in checkins:
        if check_date not in daily_records:  # 只保留每天最新的记录
            daily_records[check_date] = bool(is_early)
    
    # 将记录转换为按日期排序的列表
    sorted_records = sorted(daily_records.items(), reverse=True)
    
    streak = 0
    today = datetime.now().date()
    
    if not sorted_records:
        return 0
        
    last_date = datetime.strptime(sorted_records[0][0], '%Y-%m-%d').date()
    
    # 如果最后一次打卡不是今天或昨天，连续天数为0
    if (today - last_date).days > 1:
        return 0
        
    # 计算连续早睡天数
    for i, (check_date, is_early) in enumerate(sorted_records):
        check_date = datetime.strptime(check_date, '%Y-%m-%d').date()
        
        # 如果不是连续的日期，跳出循环
        if i > 0:
            prev_date = datetime.strptime(sorted_records[i-1][0], '%Y-%m-%d').date()
            if (prev_date - check_date).days != 1:
                break
                
        if is_early:
            streak += 1
        else:
            break
            
    return streak

@app.route('/get_streak/<username>')
def get_streak(username):
    db = get_db()
    streak = calculate_streak(db, username)
    return jsonify({'streak': streak})

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/get_all_usernames')
def get_all_usernames():
    db = get_db()
    
    # 获取所有用户名
    all_usernames = db.execute('SELECT DISTINCT username FROM checkins').fetchall()
    all_usernames = [row[0] for row in all_usernames]
    
    # 获取现有映射
    mappings = db.execute('''
        SELECT user_id, display_name, username 
        FROM user_mappings
    ''').fetchall()
    
    # 组织映射数据
    mapping_dict = defaultdict(lambda: {'display_name': '', 'usernames': []})
    mapped_usernames = set()
    
    for row in mappings:
        user_id, display_name, username = row
        mapping_dict[user_id]['display_name'] = display_name
        mapping_dict[user_id]['usernames'].append(username)
        mapped_usernames.add(username)
    
    # 获取未映射的用户名
    unassigned = [name for name in all_usernames if name not in mapped_usernames]
    
    # 准备返回数据
    result = {
        'mappings': [
            {
                'user_id': user_id,
                'display_name': data['display_name'],
                'usernames': data['usernames']
            }
            for user_id, data in mapping_dict.items()
        ],
        'unassigned': unassigned
    }
    
    return jsonify(result)

@app.route('/api/save_user_mapping', methods=['POST'])
def save_user_mapping():
    try:
        data = request.get_json()
        user_id = data['user_id']
        display_name = data['display_name']
        usernames = data['usernames']
        
        if not display_name or not usernames:
            return jsonify({'success': False, 'error': '显示名称和用户名列表不能为空'})
        
        db = get_db()
        
        # 删除该用户的现有映射
        db.execute('DELETE FROM user_mappings WHERE user_id = ?', (user_id,))
        
        # 添加新的映射
        for username in usernames:
            db.execute('''
                INSERT INTO user_mappings (user_id, display_name, username)
                VALUES (?, ?, ?)
            ''', (user_id, display_name, username))
        
        db.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def get_mapped_username(db, original_username):
    row = db.execute('''
        SELECT display_name FROM user_mappings 
        WHERE username = ?
    ''', (original_username,)).fetchone()
    return row[0] if row else original_username

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)