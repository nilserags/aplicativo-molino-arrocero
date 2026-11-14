from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Por favor inicia sesión para continuar."

try:
    from flask_migrate import Migrate
    migrate = Migrate()
except ImportError:
    class DummyMigrate:
        def init_app(self, app=None, db=None, **kwargs):
            pass
    migrate = DummyMigrate()

try:
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect()
except ImportError:
    class DummyCSRF:
        def init_app(self, app=None):
            pass
        def exempt(self, view):
            return view
    csrf = DummyCSRF()
