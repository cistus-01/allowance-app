from flask import Blueprint, jsonify
from ..database import get_db
from werkzeug.security import generate_password_hash
from datetime import date, timedelta, datetime
import random

bp = Blueprint('setup', __name__, url_prefix='/setup')

@bp.route('/init-demo')
def run():
    db = get_db()
    if db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c'] > 0:
        return jsonify({'error': 'already initialized'}), 400

    trial_ends = (datetime.utcnow() + timedelta(days=30)).isoformat()

    # 親ユーザー作成（family_idは後で設定）
    db.execute("INSERT INTO users (name, username, password_hash, role) VALUES (?,?,?,'parent')",
               ('お父さん', 'parent', generate_password_hash('demo1234')))
    db.commit()
    parent_id = db.execute("SELECT id FROM users WHERE username='parent'").fetchone()['id']

    # ファミリー作成
    db.execute(
        "INSERT INTO families (name, owner_user_id, subscription_status, trial_ends_at) VALUES (?,?,?,?)",
        ('デモ家族', parent_id, 'trial', trial_ends)
    )
    family_id = db.execute("SELECT last_insert_rowid() as id").fetchone()['id']

    # 親のfamily_idを更新
    db.execute("UPDATE users SET family_id=? WHERE id=?", (family_id, parent_id))

    # 子ユーザー（family_id付き）
    db.execute("INSERT INTO users (name, username, password_hash, role, grade, family_id) VALUES (?,?,?,'child',4,?)",
               ('たろう', 'taro', generate_password_hash('taro1234'), family_id))
    db.execute("INSERT INTO users (name, username, password_hash, role, grade, family_id) VALUES (?,?,?,'child',2,?)",
               ('はなこ', 'hanako', generate_password_hash('hanako1234'), family_id))
    db.commit()

    taro_id   = db.execute("SELECT id FROM users WHERE username='taro'").fetchone()['id']
    hanako_id = db.execute("SELECT id FROM users WHERE username='hanako'").fetchone()['id']

    for k, v, l in [('base_pay',100,'基本給'),('grade_pay_multiplier',50,'学年給'),
                    ('eval_excellent',150,'成績◎'),('eval_good',20,'成績〇'),('eval_poor',0,'成績△')]:
        db.execute("INSERT OR IGNORE INTO pay_rates (key,value,label) VALUES (?,?,?)", (k,v,l))

    for name, price, order in [('お皿洗い',50,1),('掃除機がけ',80,2),
                                ('洗濯物たたみ',30,3),('ゴミ出し',60,4),('風呂掃除',70,5)]:
        db.execute("INSERT OR IGNORE INTO chore_types (name,unit_price,sort_order) VALUES (?,?,?)", (name,price,order))
    db.commit()

    chore_ids = [r['id'] for r in db.execute("SELECT id FROM chore_types").fetchall()]
    today = date.today()
    for days_ago in range(20, 0, -1):
        d = (today - timedelta(days=days_ago)).isoformat()
        for cid in chore_ids:
            for uid in [taro_id, hanako_id]:
                if random.random() < 0.5:
                    try:
                        db.execute("INSERT INTO chore_records (user_id,chore_type_id,record_date,checked_by) VALUES (?,?,?,?)",
                                   (uid, cid, d, parent_id))
                    except Exception:
                        pass

    for i, name in enumerate(['国語','算数','理科','社会','体育','音楽','図工']):
        db.execute("INSERT OR IGNORE INTO subjects (name,sort_order) VALUES (?,?)", (name, i))
    db.commit()

    for sid in [r['id'] for r in db.execute("SELECT id FROM subjects").fetchall()]:
        try:
            db.execute("INSERT OR IGNORE INTO grade_records (user_id,subject_id,year,term,eval_1,entered_by) VALUES (?,?,?,1,?,?)",
                       (taro_id, sid, today.year, random.choice(['◎','〇','△']), parent_id))
        except Exception:
            pass

    for days_ago, uid in [(15,taro_id),(10,taro_id),(5,hanako_id)]:
        d = (today - timedelta(days=days_ago)).isoformat()
        db.execute("INSERT INTO finance_records (user_id,record_date,type,category,amount,created_by) VALUES (?,?,'income','おこづかい',1000,?)", (uid,d,parent_id))
        db.execute("INSERT INTO finance_records (user_id,record_date,type,category,amount,created_by) VALUES (?,?,'expense','お菓子',150,?)", (uid,d,parent_id))

    db.execute("INSERT INTO goals (user_id,name,target_amount,emoji) VALUES (?,?,?,?)", (taro_id,'ポケモンカードパック',3000,'🎮'))
    db.execute("INSERT INTO goals (user_id,name,target_amount,emoji) VALUES (?,?,?,?)", (taro_id,'新しい色鉛筆セット',1500,'🎨'))
    db.execute("INSERT INTO goals (user_id,name,target_amount,emoji) VALUES (?,?,?,?)", (hanako_id,'かわいい消しゴムセット',800,'🌈'))
    db.commit()

    return jsonify({'status': 'ok', 'message': 'デモデータ投入完了'})
