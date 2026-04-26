import os
import secrets
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from ..database import get_db
from ..models import User


def _send_reset_email(to_address: str, name: str, reset_url: str) -> bool:
    """パスワードリセットメールを送信。設定がない場合はFalseを返す。"""
    host = os.environ.get('SMTP_HOST', '')
    if not host:
        return False
    port     = int(os.environ.get('SMTP_PORT', 587))
    user     = os.environ.get('SMTP_USER', '')
    password = os.environ.get('SMTP_PASSWORD', '')
    from_addr = os.environ.get('FROM_EMAIL', user)

    body = f"""{name} さん

こどもの給与帳のパスワードリセットリンクをお送りします。
以下のリンクから1時間以内にパスワードを変更してください。

{reset_url}

このメールに心当たりがない場合は無視してください。

――
こどもの給与帳
"""
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = '【こどもの給与帳】パスワードリセット'
    msg['From'] = from_addr
    msg['To'] = to_address
    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.sendmail(from_addr, [to_address], msg.as_string())
        return True
    except Exception:
        return False

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if row and check_password_hash(row['password_hash'], password):
            user = User(row)
            login_user(user, remember=True)
            return redirect(url_for('home.index'))
        flash('ユーザー名またはパスワードが違います。', 'danger')

    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@bp.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if current_user.is_authenticated:
        return redirect(url_for('home.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE email = ? AND role = 'parent'", (email,)).fetchone()
        if row:
            token = secrets.token_urlsafe(32)
            expires = datetime.utcnow() + timedelta(hours=1)
            db.execute(
                'INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)',
                (row['id'], token, expires.isoformat())
            )
            db.commit()
            reset_url = url_for('auth.reset', token=token, _external=True)
            email_sent = _send_reset_email(email, row['name'], reset_url)
            return render_template('auth/forgot_sent.html',
                                   reset_url=reset_url,
                                   name=row['name'],
                                   email_sent=email_sent,
                                   email=email)
        flash('そのメールアドレスは登録されていません。', 'danger')

    return render_template('auth/forgot.html')

@bp.route('/reset/<token>', methods=['GET', 'POST'])
def reset(token):
    if current_user.is_authenticated:
        return redirect(url_for('home.index'))

    db = get_db()
    row = db.execute(
        'SELECT * FROM password_reset_tokens WHERE token = ? AND used_at IS NULL',
        (token,)
    ).fetchone()

    if not row or datetime.fromisoformat(row['expires_at']) < datetime.utcnow():
        flash('このリセットリンクは無効または期限切れです。', 'danger')
        return redirect(url_for('auth.forgot'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if len(password) < 6:
            flash('パスワードは6文字以上にしてください。', 'danger')
            return render_template('auth/reset.html', token=token)
        if password != confirm:
            flash('パスワードが一致しません。', 'danger')
            return render_template('auth/reset.html', token=token)

        db.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                   (generate_password_hash(password), row['user_id']))
        db.execute('UPDATE password_reset_tokens SET used_at = ? WHERE token = ?',
                   (datetime.utcnow().isoformat(), token))
        db.commit()
        flash('パスワードを変更しました。ログインしてください。', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset.html', token=token)
