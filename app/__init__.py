import os
from flask import Flask
from flask_login import LoginManager
from .database import init_db, get_db
from .models import User

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'allowance-app-secret-2026')

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'ログインしてください。'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        db = get_db()
        row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None:
            return None
        return User(row)

    with app.app_context():
        init_db()
        from .routes import auth, home, chores, grades, finance, admin, goals, setup, register, billing, seo, jarvis, onboarding, stats
        app.register_blueprint(auth.bp)
        app.register_blueprint(home.bp)
        app.register_blueprint(chores.bp)
        app.register_blueprint(grades.bp)
        app.register_blueprint(finance.bp)
        app.register_blueprint(admin.bp)
        app.register_blueprint(goals.bp)
        app.register_blueprint(setup.bp)
        app.register_blueprint(register.bp)
        app.register_blueprint(billing.bp)
        app.register_blueprint(seo.bp)
        app.register_blueprint(jarvis.bp)
        app.register_blueprint(onboarding.bp)
        app.register_blueprint(stats.bp)

    return app
