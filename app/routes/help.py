from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from ..database import get_db

bp = Blueprint('help', __name__, url_prefix='/help')


@bp.route('/')
@login_required
def index():
    return render_template('help/index.html')


@bp.route('/tutorial')
@login_required
def tutorial():
    return render_template('help/tutorial.html')


@bp.route('/tutorial/done', methods=['POST'])
@login_required
def tutorial_done():
    db = get_db()
    db.execute('UPDATE users SET tutorial_done=1 WHERE id=?', (current_user.id,))
    db.commit()
    redirect_to = request.form.get('next', url_for('home.index'))
    return redirect(redirect_to)
