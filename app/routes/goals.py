from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ..database import get_db
from ..salary import calc_balance

bp = Blueprint('goals', __name__, url_prefix='/goals')

@bp.route('/')
@login_required
def index():
    db = get_db()
    if current_user.is_parent:
        child_id = request.args.get('child_id', type=int)
        children = db.execute("SELECT * FROM users WHERE role='child' ORDER BY grade DESC").fetchall()
        if child_id is None and children:
            child_id = children[0]['id']
        target_id = child_id
        target_user = db.execute('SELECT * FROM users WHERE id=?', (target_id,)).fetchone() if target_id else None
    else:
        target_id = current_user.id
        target_user = None
        children = None

    goals = []
    balance = 0
    if target_id:
        goals = db.execute(
            'SELECT * FROM goals WHERE user_id=? ORDER BY is_achieved ASC, created_at DESC',
            (target_id,)
        ).fetchall()
        balance = calc_balance(target_id)

    return render_template('goals/index.html',
                           goals=goals,
                           balance=balance,
                           target_id=target_id,
                           target_user=target_user,
                           children=children if current_user.is_parent else None)

@bp.route('/add', methods=['POST'])
@login_required
def add():
    db = get_db()
    if current_user.is_parent:
        target_id = request.form.get('child_id', type=int)
    else:
        target_id = current_user.id

    name = request.form.get('name', '').strip()
    target_amount = request.form.get('target_amount', type=int)
    emoji = request.form.get('emoji', '🎯').strip() or '🎯'

    if not name or not target_amount or target_amount <= 0:
        flash('ほしいものの名前と金額を入力してください。', 'danger')
        return redirect(url_for('goals.index', child_id=target_id if current_user.is_parent else None))

    db.execute(
        'INSERT INTO goals (user_id, name, target_amount, emoji) VALUES (?, ?, ?, ?)',
        (target_id, name, target_amount, emoji)
    )
    db.commit()
    flash(f'「{name}」を目標に追加しました！', 'success')
    return redirect(url_for('goals.index', child_id=target_id if current_user.is_parent else None))

@bp.route('/achieve/<int:goal_id>', methods=['POST'])
@login_required
def achieve(goal_id):
    if not current_user.is_parent:
        flash('親のみ達成にできます。', 'danger')
        return redirect(url_for('goals.index'))

    db = get_db()
    goal = db.execute('SELECT * FROM goals WHERE id=?', (goal_id,)).fetchone()
    if goal:
        db.execute(
            "UPDATE goals SET is_achieved=1, achieved_at=CURRENT_TIMESTAMP WHERE id=?",
            (goal_id,)
        )
        db.commit()
        flash(f'🎉「{goal["name"]}」達成おめでとう！', 'success')
        return redirect(url_for('goals.index', child_id=goal['user_id']))

    return redirect(url_for('goals.index'))

@bp.route('/delete/<int:goal_id>', methods=['POST'])
@login_required
def delete(goal_id):
    db = get_db()
    goal = db.execute('SELECT * FROM goals WHERE id=?', (goal_id,)).fetchone()
    if goal:
        if current_user.is_child and goal['user_id'] != current_user.id:
            flash('権限がありません。', 'danger')
            return redirect(url_for('goals.index'))
        db.execute('DELETE FROM goals WHERE id=?', (goal_id,))
        db.commit()
        flash('目標を削除しました。', 'success')
        return redirect(url_for('goals.index',
                                child_id=goal['user_id'] if current_user.is_parent else None))

    return redirect(url_for('goals.index'))
