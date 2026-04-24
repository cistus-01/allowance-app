from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from ..database import get_db
from ..models import User

bp = Blueprint('register', __name__, url_prefix='/register')

@bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        family_name = request.form.get('family_name', '').strip()
        parent_name = request.form.get('parent_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not all([family_name, parent_name, username, email, password]):
            flash('すべての項目を入力してください。', 'danger')
            return render_template('register/index.html')

        if len(password) < 6:
            flash('パスワードは6文字以上にしてください。', 'danger')
            return render_template('register/index.html')

        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing:
            flash('そのユーザー名はすでに使われています。', 'danger')
            return render_template('register/index.html')

        email_taken = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if email_taken:
            flash('そのメールアドレスはすでに登録されています。', 'danger')
            return render_template('register/index.html')

        trial_ends = datetime.utcnow() + timedelta(days=30)

        # ファミリー作成（owner_user_idは後で更新）
        db.execute(
            '''INSERT INTO families (name, owner_user_id, subscription_status, trial_ends_at)
               VALUES (?, 0, 'trial', ?)''',
            (family_name, trial_ends.isoformat())
        )
        family_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # 親ユーザー作成
        db.execute(
            '''INSERT INTO users (name, username, email, password_hash, role, family_id)
               VALUES (?, ?, ?, ?, 'parent', ?)''',
            (parent_name, username, email, generate_password_hash(password), family_id)
        )
        user_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # ファミリーのowner_user_idを更新
        db.execute('UPDATE families SET owner_user_id = ? WHERE id = ?', (user_id, family_id))
        db.commit()

        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        login_user(User(row), remember=True)

        flash(f'ご登録ありがとうございます！30日間の無料トライアルが始まりました。', 'success')
        return redirect(url_for('onboarding.index'))

    return render_template('register/index.html')
