import os
import json
import random
from datetime import date, timedelta
from flask import Flask, redirect, url_for, request, flash
from flask_login import current_user

# Carga de variables de entorno seguras (.env)
try:
    from dotenv import load_dotenv
    # Buscar .env en el directorio actual y en la raíz del proyecto
    load_dotenv()
    ruta_env_padre = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(ruta_env_padre):
        load_dotenv(ruta_env_padre)
except ImportError:
    pass

from extensions import db, login_manager, migrate, csrf
from models import Usuario, Equipo, RegistroMantenimiento, RegistroConsumo, ROL_TECNICO, ROL_ENCARGADO
from routes.auth import auth_bp
from routes.tecnico import tecnico_bp
from routes.encargado import encargado_bp


def crear_app():
    app = Flask(__name__)

    # Configuración de modo de ejecución ('demo' o 'production')
    app_mode = os.environ.get("APP_MODE", "demo").strip().lower()
    app.config["APP_MODE"] = app_mode

    # Clave secreta obtenida obligatoriamente de variables de entorno en producción
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        if app_mode == "production":
            raise RuntimeError(
                "ERROR DE SEGURIDAD: SECRET_KEY no está configurada en las variables de entorno. "
                "Cree un archivo .env con una SECRET_KEY segura para operar en producción."
            )
        secret_key = "molino-la-corona-dev-key-temporary-change-in-env"
    app.config["SECRET_KEY"] = secret_key

    # Depuración deshabilitada por defecto (debug=False)
    debug_val = os.environ.get("FLASK_DEBUG", "False").strip().lower() in ("true", "1", "t", "yes")
    app.config["DEBUG"] = debug_val

    # Asegurar que el directorio de la base de datos exista
    os.makedirs(app.instance_path, exist_ok=True)
    db_path = os.path.join(app.instance_path, "mantenimiento.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{db_path}")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Inicialización de extensiones (SQLAlchemy, Login, Flask-Migrate y Protección CSRF)
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(tecnico_bp)
    app.register_blueprint(encargado_bp)

    @login_manager.user_loader
    def cargar_usuario(user_id):
        return db.session.get(Usuario, int(user_id))

    @app.before_request
    def verificar_cambio_password_obligatorio():
        """Fuerza al usuario a cambiar su contraseña si tiene activa la bandera de primer ingreso (1234)."""
        if current_user.is_authenticated and getattr(current_user, "debe_cambiar_password", False):
            endpoint = request.endpoint or ""
            rutas_permitidas = ("auth.cambiar_password", "auth.logout", "static")
            if not any(endpoint == r or endpoint.startswith(r) for r in rutas_permitidas):
                flash("Por seguridad institucional, debe actualizar su contraseña inicial antes de operar el sistema.", "warning")
                return redirect(url_for("auth.cambiar_password"))

    @app.context_processor
    def inyectar_contexto_encargado():
        """Inyecta contadores en tiempo real, alertas de modo demo/producción y KPIs."""
        contexto = {
            "app_mode": app.config.get("APP_MODE", "demo"),
            "sidebar_kpis": {},
        }
        if current_user.is_authenticated and current_user.rol == ROL_ENCARGADO:
            try:
                todos = Equipo.query.all()
                vencidos = [e for e in todos if e.nivel_urgencia() == "alta"]
                proximos = [e for e in todos if e.nivel_urgencia() == "media"]
                al_dia = [e for e in todos if e.nivel_urgencia() == "baja"]
                pendientes = RegistroMantenimiento.query.filter_by(validado=False).count()
                contexto["sidebar_kpis"] = {
                    "total_motores": len(todos),
                    "alta": len(vencidos),
                    "media": len(proximos),
                    "baja": len(al_dia),
                    "pendientes": pendientes,
                    "vencidos_muestra": vencidos[:6],
                }
            except Exception:
                pass
        return contexto

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            if current_user.rol == ROL_ENCARGADO:
                return redirect(url_for("encargado.dashboard"))
            return redirect(url_for("tecnico.registrar"))
        return redirect(url_for("auth.login"))

    return app


def generar_parque_130_motores():
    """
    Genera el inventario completo y realista de 130 motores eléctricos de Molino La Corona
    distribuidos en las 5 áreas principales del proceso de pilado de arroz.
    Incluye motores pesados de hasta 80 HP y potencias intermedias (50, 40, 30, 25, 20, 15, 10, 7.5, 5 HP).
    """
    motores = []

    # 1. LÍNEA DE BLANQUEO Y PULIDO (25 motores) — Mayor potencia: motores de 80 HP y 75 HP
    blanqueo_def = [
        ("M-001", "Motor Blanqueador Vertical N°1", 80.0, "WEG", "W22 Super Premium", 60),
        ("M-002", "Motor Blanqueador Vertical N°2", 80.0, "WEG", "W22 Super Premium", 60),
        ("M-003", "Motor Blanqueador Vertical N°3", 80.0, "Siemens", "Simotics 1LE1", 60),
        ("M-004", "Motor Blanqueador Horizontal N°1", 60.0, "ABB", "M3BP Heavy Duty", 90),
        ("M-005", "Motor Blanqueador Horizontal N°2", 60.0, "ABB", "M3BP Heavy Duty", 90),
        ("M-006", "Motor Pulidora de Agua N°1 (Water Polisher)", 75.0, "WEG", "W22 Cast Iron", 75),
        ("M-007", "Motor Pulidora de Agua N°2 (Water Polisher)", 75.0, "Siemens", "Simotics GP", 75),
        ("M-008", "Motor Ciclón Extractor de Polvillo 1", 40.0, "Delcrosa", "TRI-H", 90),
        ("M-009", "Motor Ciclón Extractor de Polvillo 2", 40.0, "Delcrosa", "TRI-H", 90),
        ("M-010", "Motor Ventilador de Enfriamiento de Grano 1", 30.0, "WEG", "W21", 90),
        ("M-011", "Motor Ventilador de Enfriamiento de Grano 2", 30.0, "WEG", "W21", 90),
        ("M-012", "Motor Elevador de Arroz Pulido a Silo Intermedio", 25.0, "Siemens", "1LE0", 90),
        ("M-013", "Motor Elevador de Arroz Pulido a Tolva Pulmón", 25.0, "Siemens", "1LE0", 90),
        ("M-014", "Motor Transportador Helicoidal de Polvillo Grueso", 20.0, "Delcrosa", "TRI-S", 120),
        ("M-015", "Motor Transportador Helicoidal de Polvillo Fino", 20.0, "Delcrosa", "TRI-S", 120),
        ("M-016", "Motor Compresor de Limpieza Neumática Blanqueo", 50.0, "Atlas Copco", "GA-37", 90),
        ("M-017", "Motor Dosificador de Salvado y Polvillo", 10.0, "WEG", "W21", 120),
        ("M-018", "Motor Bomba de Inyección de Agua Microaspersión", 7.5, "Pedrollo", "F-50", 90),
        ("M-019", "Motor Filtro de Mangas Aspiración Central", 30.0, "ABB", "M2BAX", 90),
        ("M-020", "Motor Esclusa Rotativa Descarga de Polvillo 1", 5.0, "Delcrosa", "M-MR", 120),
        ("M-021", "Motor Esclusa Rotativa Descarga de Polvillo 2", 5.0, "Delcrosa", "M-MR", 120),
        ("M-022", "Motor Ventilador Disipador de Fricción Blanqueador 1", 15.0, "WEG", "W21", 90),
        ("M-023", "Motor Ventilador Disipador de Fricción Blanqueador 2", 15.0, "WEG", "W21", 90),
        ("M-024", "Motor Elevador de Retorno de Arroz Mal Pulido", 20.0, "Siemens", "1LE0", 90),
        ("M-025", "Motor Colector de Muestreo Automático Blanqueo", 3.0, "WEG", "W20", 180),
    ]
    for cod, nom, hp, mrc, mod, freq in blanqueo_def:
        motores.append(Equipo(
            codigo=cod, nombre=nom, area="blanqueo", frecuencia_mantenimiento_dias=freq,
            marca=mrc, modelo=mod, potencia_hp=hp, potencia_kw=round(hp * 0.7457, 1),
            anio_instalacion=random.choice([2019, 2020, 2021, 2022, 2023]),
            horas_uso_dia=random.choice([16.0, 18.0, 20.0, 22.0]),
        ))

    # 2. LÍNEA DE DESCASCARADO Y SEPARACIÓN PADDY (30 motores)
    descascarado_def = [
        ("M-026", "Motor Ciclón Extractor de Cascarilla Principal", 80.0, "WEG", "W22 High Efficiency", 60),
        ("M-027", "Motor Descascaradora de Rodillos de Goma 1", 50.0, "Siemens", "Simotics 1LE1", 60),
        ("M-028", "Motor Descascaradora de Rodillos de Goma 2", 50.0, "Siemens", "Simotics 1LE1", 60),
        ("M-029", "Motor Descascaradora de Rodillos de Goma 3", 50.0, "WEG", "W22", 60),
        ("M-030", "Motor Separador de Cascarilla por Aire N°1", 40.0, "ABB", "M3BP", 75),
        ("M-031", "Motor Separador de Cascarilla por Aire N°2", 40.0, "ABB", "M3BP", 75),
        ("M-032", "Motor Mesa Separadora Paddy N°1 (Densimétrica)", 15.0, "Delcrosa", "TRI-H", 90),
        ("M-033", "Motor Mesa Separadora Paddy N°2 (Densimétrica)", 15.0, "Delcrosa", "TRI-H", 90),
        ("M-034", "Motor Mesa Separadora Paddy N°3 (Densimétrica)", 15.0, "WEG", "W21", 90),
        ("M-035", "Motor Mesa Separadora Paddy N°4 (Densimétrica)", 15.0, "WEG", "W21", 90),
        ("M-036", "Motor Ventilador Presurizador Cascarilla a Silo", 50.0, "Siemens", "1LE1", 75),
        ("M-037", "Motor Elevador de Arroz Cáscara a Descascaradoras", 30.0, "ABB", "M2BAX", 90),
        ("M-038", "Motor Elevador de Arroz Integral (Brown Rice)", 30.0, "ABB", "M2BAX", 90),
        ("M-039", "Motor Elevador de Retorno Paddy a Descascarado", 25.0, "Siemens", "1LE0", 90),
        ("M-040", "Motor Sinfín Colector de Cascarilla de Arroz", 25.0, "Delcrosa", "TRI-S", 90),
        ("M-041", "Motor Transportador Neumático a Caldera", 40.0, "WEG", "W22", 90),
        ("M-042", "Motor Zaranda Limpiadora de Grano Integral 1", 20.0, "Siemens", "1LE0", 90),
        ("M-043", "Motor Zaranda Limpiadora de Grano Integral 2", 20.0, "Siemens", "1LE0", 90),
        ("M-044", "Motor Compresor de Regulación de Presión de Rodillos", 30.0, "Kaeser", "SK-25", 90),
        ("M-045", "Motor Dosificador Gravimétrico de Paddy", 7.5, "WEG", "W21", 120),
        ("M-046", "Motor Ventilador Auxiliar Extractor de Polvo Fino", 15.0, "Delcrosa", "TRI-H", 90),
        ("M-047", "Motor Esclusa de Cascarilla Quemador", 7.5, "Delcrosa", "M-MR", 120),
        ("M-048", "Motor Esclusa Ciclón Secundario Descascarado", 7.5, "Delcrosa", "M-MR", 120),
        ("M-049", "Motor Agitador de Tolva Reguladora Integral", 10.0, "Siemens", "1LE0", 120),
        ("M-050", "Motor Vibrador de Mesa Despedradora Paddy", 10.0, "WEG", "W21", 90),
        ("M-051", "Motor Sinfín de Distribución a Mesas Paddy", 15.0, "Delcrosa", "TRI-S", 120),
        ("M-052", "Motor Filtro Colector de Impurezas Ligeras", 20.0, "ABB", "M2BAX", 90),
        ("M-053", "Motor Elevador Auxiliar de Mantenimiento Descascarado", 15.0, "Siemens", "1LE0", 120),
        ("M-054", "Motor Extractor de Vapores Térmicos Rodillos", 10.0, "WEG", "W20", 90),
        ("M-055", "Motor Sensor de Carga Continua Descascarado", 3.0, "ABB", "M2AA", 180),
    ]
    for cod, nom, hp, mrc, mod, freq in descascarado_def:
        motores.append(Equipo(
            codigo=cod, nombre=nom, area="descascarado", frecuencia_mantenimiento_dias=freq,
            marca=mrc, modelo=mod, potencia_hp=hp, potencia_kw=round(hp * 0.7457, 1),
            anio_instalacion=random.choice([2018, 2019, 2020, 2021, 2022]),
            horas_uso_dia=random.choice([16.0, 18.0, 20.0]),
        ))

    # 3. LÍNEA DE SECADO Y SILOS DE ALMACENAMIENTO (30 motores)
    secado_def = [
        ("M-056", "Motor Turbina Centrífuga Secador de Columna Torre A", 60.0, "WEG", "W22 Cast Iron", 60),
        ("M-057", "Motor Turbina Centrífuga Secador de Columna Torre B", 60.0, "WEG", "W22 Cast Iron", 60),
        ("M-058", "Motor Turbina Centrífuga Secador de Columna Torre C", 60.0, "Siemens", "1LE1", 60),
        ("M-059", "Motor Ventilador Axial Inyección Aire Caliente 1", 50.0, "Siemens", "1LE1", 75),
        ("M-060", "Motor Ventilador Axial Inyección Aire Caliente 2", 50.0, "ABB", "M3BP", 75),
        ("M-061", "Motor Ventilador Axial Inyección Aire Caliente 3", 50.0, "ABB", "M3BP", 75),
        ("M-062", "Motor Elevador Principal de Arroz Húmedo (Paddy)", 40.0, "Delcrosa", "TRI-H", 90),
        ("M-063", "Motor Elevador de Recirculación Torre de Secado A", 30.0, "Delcrosa", "TRI-H", 90),
        ("M-064", "Motor Elevador de Recirculación Torre de Secado B", 30.0, "WEG", "W21", 90),
        ("M-065", "Motor Elevador de Recirculación Torre de Secado C", 30.0, "WEG", "W21", 90),
        ("M-066", "Motor Elevador Carga a Batería de Silos Metálicos", 40.0, "Siemens", "1LE1", 90),
        ("M-067", "Motor Ventilador Aireación Silo Vertical N°1", 25.0, "WEG", "W21", 90),
        ("M-068", "Motor Ventilador Aireación Silo Vertical N°2", 25.0, "WEG", "W21", 90),
        ("M-069", "Motor Ventilador Aireación Silo Vertical N°3", 25.0, "Siemens", "1LE0", 90),
        ("M-070", "Motor Ventilador Aireación Silo Vertical N°4", 25.0, "Siemens", "1LE0", 90),
        ("M-071", "Motor Ventilador Aireación Silo Vertical N°5", 25.0, "ABB", "M2BAX", 90),
        ("M-072", "Motor Ventilador Aireación Silo Vertical N°6", 25.0, "ABB", "M2BAX", 90),
        ("M-073", "Motor Sinfín Barredor de Descarga de Fondo Silo 1", 20.0, "Delcrosa", "TRI-S", 120),
        ("M-074", "Motor Sinfín Barredor de Descarga de Fondo Silo 2", 20.0, "Delcrosa", "TRI-S", 120),
        ("M-075", "Motor Sinfín Barredor de Descarga de Fondo Silo 3", 20.0, "Delcrosa", "TRI-S", 120),
        ("M-076", "Motor Sinfín Barredor de Descarga de Fondo Silo 4", 20.0, "WEG", "W21", 120),
        ("M-077", "Motor Banda Transportadora Túnel Inferior Silos", 30.0, "Siemens", "1LE0", 90),
        ("M-078", "Motor Quemador Automático de Cascarilla Torre A", 15.0, "Delcrosa", "TRI-H", 90),
        ("M-079", "Motor Quemador Automático de Cascarilla Torre B", 15.0, "Delcrosa", "TRI-H", 90),
        ("M-080", "Motor Extractor de Cenizas y Escoria de Horno", 10.0, "WEG", "W21", 120),
        ("M-081", "Motor Compuerta de Descarga Neumática Torre A", 7.5, "Siemens", "1LE0", 120),
        ("M-082", "Motor Compuerta de Descarga Neumática Torre B", 7.5, "Siemens", "1LE0", 120),
        ("M-083", "Motor Dosificador de Flujo Continuo de Secado", 10.0, "ABB", "M2BAX", 120),
        ("M-084", "Motor Extractor de Polvo de Descarga de Silos", 20.0, "WEG", "W21", 90),
        ("M-085", "Motor Agitador de Tolva de Recepción Secador", 10.0, "Delcrosa", "TRI-S", 120),
    ]
    for cod, nom, hp, mrc, mod, freq in secado_def:
        motores.append(Equipo(
            codigo=cod, nombre=nom, area="secado", frecuencia_mantenimiento_dias=freq,
            marca=mrc, modelo=mod, potencia_hp=hp, potencia_kw=round(hp * 0.7457, 1),
            anio_instalacion=random.choice([2019, 2020, 2021, 2022]),
            horas_uso_dia=random.choice([14.0, 16.0, 18.0, 24.0]),
        ))

    # 4. RECEPCIÓN, TOLVAS Y PRELIMPIEZA (25 motores)
    prelimpieza_def = [
        ("M-086", "Motor Zaranda Limpiadora de Tambor Rotativo Principal", 30.0, "Delcrosa", "TRI-H", 90),
        ("M-087", "Motor Zaranda Despedradora por Gravedad 1", 25.0, "WEG", "W22", 90),
        ("M-088", "Motor Zaranda Despedradora por Gravedad 2", 25.0, "WEG", "W22", 90),
        ("M-089", "Motor Elevador Principal de Cangilones Tolva Descarga", 30.0, "Siemens", "Simotics 1LE1", 90),
        ("M-090", "Motor Aspirador Ciclónico de Paja y Polvo Volátil", 40.0, "ABB", "M3BP", 90),
        ("M-091", "Motor Banda Transportadora Descarga Rápida Tolva 1", 20.0, "Delcrosa", "TRI-S", 120),
        ("M-092", "Motor Banda Transportadora Descarga Rápida Tolva 2", 20.0, "Delcrosa", "TRI-S", 120),
        ("M-093", "Motor Criba Vibratoria para Separación de Paja Larga", 15.0, "WEG", "W21", 90),
        ("M-094", "Motor Separador Magnético de Impurezas Metálicas", 10.0, "Siemens", "1LE0", 120),
        ("M-095", "Motor Ventilador de Aspiración en Tolva de Volquete", 30.0, "ABB", "M2BAX", 90),
        ("M-096", "Motor Sinfín Alimentador a Zarandas Prelimpiadoras", 20.0, "Delcrosa", "TRI-S", 120),
        ("M-097", "Motor Elevador de Impurezas Pesadas a Contenedor", 15.0, "WEG", "W21", 120),
        ("M-098", "Motor Esclusa de Descarga de Polvo de Prelimpieza", 7.5, "Delcrosa", "M-MR", 120),
        ("M-099", "Motor Vibrador de Descarga Rápida de Tolva Pulmón", 10.0, "WEG", "W21", 90),
        ("M-100", "Motor Filtro de Mangas Sistema de Recepción", 25.0, "Siemens", "1LE0", 90),
        ("M-101", "Motor Sinfín Colector de Tierra y Arena de Grano", 15.0, "Delcrosa", "TRI-S", 120),
        ("M-102", "Motor Ventilador de Cortina de Aire en Tolva", 20.0, "ABB", "M2BAX", 90),
        ("M-103", "Motor Elevador Auxiliar de Tolva de Muestreo", 10.0, "WEG", "W20", 120),
        ("M-104", "Motor Compuerta Hidráulica de Dosificación de Tolva", 10.0, "Rexroth", "A10V", 90),
        ("M-105", "Motor Desgranador Auxiliar de Espigas", 15.0, "Siemens", "1LE0", 90),
        ("M-106", "Motor Transportador Reversible a Silo Pulmón", 20.0, "Delcrosa", "TRI-S", 120),
        ("M-107", "Motor Bomba Hidráulica Plataforma Basculante 1", 30.0, "Vickers", "PVB-45", 90),
        ("M-108", "Motor Bomba Hidráulica Plataforma Basculante 2", 30.0, "Vickers", "PVB-45", 90),
        ("M-109", "Motor Extractor de Polvo de Fosa de Balanza", 15.0, "WEG", "W21", 90),
        ("M-110", "Motor Compresor de Limpieza Neumática Recepción", 25.0, "Kaeser", "SK-22", 90),
    ]
    for cod, nom, hp, mrc, mod, freq in prelimpieza_def:
        motores.append(Equipo(
            codigo=cod, nombre=nom, area="prelimpieza", frecuencia_mantenimiento_dias=freq,
            marca=mrc, modelo=mod, potencia_hp=hp, potencia_kw=round(hp * 0.7457, 1),
            anio_instalacion=random.choice([2019, 2020, 2021, 2022]),
            horas_uso_dia=random.choice([10.0, 12.0, 14.0, 16.0]),
        ))

    # 5. CLASIFICACIÓN POR TAMAÑO, SELECCIÓN ÓPTICA Y ENSACADO (20 motores)
    clasificacion_def = [
        ("M-111", "Motor Compresor de Tornillo Selectora Óptica 1 (Sortex)", 60.0, "Atlas Copco", "GA-45 VSD", 60),
        ("M-112", "Motor Compresor de Tornillo Selectora Óptica 2", 50.0, "Sullair", "S-Energy 37", 60),
        ("M-113", "Motor Clasificador Cilíndrico Trieur 1 (Arroz Entero)", 25.0, "Delcrosa", "TRI-H", 90),
        ("M-114", "Motor Clasificador Cilíndrico Trieur 2 (Separación Granillo)", 25.0, "Delcrosa", "TRI-H", 90),
        ("M-115", "Motor Planosifter Clasificador de Malla Múltiple 1", 20.0, "Siemens", "1LE1", 90),
        ("M-116", "Motor Planosifter Clasificador de Malla Múltiple 2", 20.0, "Siemens", "1LE1", 90),
        ("M-117", "Motor Mesa Densimétrica Clasificadora Extra/Superior", 15.0, "WEG", "W22", 90),
        ("M-118", "Motor Mesa Densimétrica de Grano Quebrado (Arrocillo)", 15.0, "WEG", "W22", 90),
        ("M-119", "Motor Elevador de Grano Entero a Selectora Óptica", 20.0, "ABB", "M2BAX", 90),
        ("M-120", "Motor Elevador de Arroz Seleccionado a Silos de Ensacado", 20.0, "ABB", "M2BAX", 90),
        ("M-121", "Motor Elevador de Arrocillo y Subproductos a Tolvas", 15.0, "Siemens", "1LE0", 90),
        ("M-122", "Motor Aspirador de Partículas de Pulido en Sortex", 25.0, "WEG", "W21", 90),
        ("M-123", "Motor Ensacadora Automática de Sacos de 50 kg N°1", 10.0, "Siemens", "1LE0", 120),
        ("M-124", "Motor Ensacadora Automática de Sacos de 50 kg N°2", 10.0, "Siemens", "1LE0", 120),
        ("M-125", "Motor Cosedora y Transportador de Sacos Llenos 1", 7.5, "Delcrosa", "TRI-S", 120),
        ("M-126", "Motor Cosedora y Transportador de Sacos Llenos 2", 7.5, "Delcrosa", "TRI-S", 120),
        ("M-127", "Motor Envasadora Fraccionada 1 kg y 5 kg", 15.0, "WEG", "W21", 90),
        ("M-128", "Motor Banda Transportadora a Zona de Estiba y Despacho", 15.0, "Delcrosa", "TRI-S", 120),
        ("M-129", "Motor Secador Frigorífico de Aire Comprimido Sortex", 15.0, "Atlas Copco", "FD-120", 90),
        ("M-130", "Motor Extractor General de Polvillo Sala de Ensacado", 20.0, "ABB", "M2BAX", 90),
    ]
    for cod, nom, hp, mrc, mod, freq in clasificacion_def:
        motores.append(Equipo(
            codigo=cod, nombre=nom, area="clasificacion", frecuencia_mantenimiento_dias=freq,
            marca=mrc, modelo=mod, potencia_hp=hp, potencia_kw=round(hp * 0.7457, 1),
            anio_instalacion=random.choice([2020, 2021, 2022, 2023]),
            horas_uso_dia=random.choice([12.0, 14.0, 16.0, 18.0]),
        ))

    return motores


def poblar_datos_iniciales():
    """
    Inicializa los datos del sistema respetando la configuración de entorno (APP_MODE):
    - En producción ('production'): Crea únicamente los 130 motores y los dos usuarios
      iniciales (con bandera de cambio obligatorio de contraseña). Base de datos limpia.
    - En demostración ('demo'): Añade registros históricos calibrados de 24 meses (kWh,
      facturación ~S/. 70k, semáforo) para propósitos de sustentación académica y pruebas.
    """
    if Usuario.query.first():
        return  # ya hay datos, no duplicar

    tecnico = Usuario(
        nombre_completo="Técnico de Mantenimiento",
        username="tecnico1",
        rol=ROL_TECNICO,
        debe_cambiar_password=True,
    )
    tecnico.set_password("1234")

    encargado = Usuario(
        nombre_completo="Encargado de Auditoría y Mantenimiento",
        username="encargado1",
        rol=ROL_ENCARGADO,
        debe_cambiar_password=True,
    )
    encargado.set_password("1234")

    db.session.add_all([tecnico, encargado])
    db.session.commit()

    # Generar los 130 motores de Molino La Corona (común a producción y demo)
    equipos = generar_parque_130_motores()
    db.session.add_all(equipos)
    db.session.commit()

    app_mode = os.environ.get("APP_MODE", "demo").strip().lower()
    if app_mode == "production":
        print("Base de datos inicializada en MODO PRODUCCIÓN:")
        print(" - 130 motores industriales registrados en limpio.")
        print(" - 2 usuarios iniciales creados (tecnico1 / encargado1) con cambio obligatorio de contraseña.")
        print(" - Base de datos limpia sin registros de mantenimiento ni consumos ficticios.")
        return

    # --- CALIBRACIÓN DEL SEMÁFORO DE 3 COLORES ---
    # Queremos una distribución visual representativa sobre los 130 motores:
    # 🔴 Urgencia Alta (Vencidos / <= 0 días restantes): ~14 motores
    # 🟡 Urgencia Media (Próximos / 1 a 15 días restantes): ~24 motores
    # 🟢 Urgencia Baja (Al Día / > 15 días restantes): ~92 motores
    hoy = date.today()
    random.seed(42)

    tipos = ["preventivo", "correctivo"]
    hallazgos_preventivos = [
        "Mantenimiento rutinario ejecutado: lubricación de rodamientos con grasa de alta temperatura y medición de vibraciones dentro de norma ISO 10816.",
        "Limpieza de aletas de disipación térmica, reapriete de bornes eléctricos y verificación de aislamiento con megóhmetro (resultado > 50 MΩ).",
        "Alineación láser de acoplamiento motor-carga y cambio de sellos guardapolvo en tapas porta-rodamientos.",
        "Inspección preventiva completada: corriente por fase balanceada y temperatura de carcasa estable en 58 °C.",
        "Cambio preventivo de fajas de transmisión en V y ajuste de tensión con tensiómetro sónico.",
        "Revisión de conexiones en caja de bornes, reapriete con torquímetro y ajuste de contactor en arrancador suave.",
    ]
    hallazgos_correctivos = [
        "Ruido anormal y juego axial en rodamiento 6314-2RS; se programó cambio de rodamientos por desgaste severo.",
        "Sobrecalentamiento por sobrecorriente en devanado; se detectó desbalance de tensión de 4.2% entre fases.",
        "Vibración severa por desbalanceo en polea motriz; balanceo dinámico y ajuste de chaveta ejecutados.",
        "Falla de ventilador de enfriamiento fracturado por fatiga de material; sustitución inmediata realizada.",
    ]

    for idx, eq in enumerate(equipos):
        freq = eq.frecuencia_mantenimiento_dias
        # Decidir en qué semáforo colocar este motor:
        if idx in [0, 2, 7, 15, 26, 31, 40, 56, 61, 75, 86, 92, 111, 115]:
            # 🔴 URGENCIA ALTA: Días pasados superan la frecuencia (vencido entre 5 y 35 días)
            dias_atras = freq + random.randint(5, 35)
            tipo_m = "correctivo" if random.random() < 0.4 else "preventivo"
            hallazgo = random.choice(hallazgos_correctivos) if tipo_m == "correctivo" else random.choice(hallazgos_preventivos)
        elif idx in [1, 5, 8, 12, 19, 27, 33, 37, 43, 50, 58, 64, 70, 78, 83, 89, 95, 100, 107, 112, 116, 120, 124, 128]:
            # 🟡 URGENCIA MEDIA: Faltan entre 2 y 14 días para vencer
            dias_atras = freq - random.randint(2, 14)
            tipo_m = "preventivo"
            hallazgo = random.choice(hallazgos_preventivos)
        else:
            # 🟢 URGENCIA BAJA: Al día, faltan entre 20 y (freq - 15) días
            dias_atras = random.randint(5, max(15, freq - 20))
            tipo_m = "preventivo"
            hallazgo = random.choice(hallazgos_preventivos)

        fecha_maint = hoy - timedelta(days=dias_atras)
        is_corr = (tipo_m == "correctivo")
        vib_ant = round(random.uniform(5.2, 7.8), 2) if is_corr else round(random.uniform(2.6, 3.8), 2)
        vib_des = round(random.uniform(1.3, 2.1), 2) if is_corr else round(random.uniform(1.1, 1.7), 2)
        temp_ant = round(random.uniform(74.0, 86.0), 1) if is_corr else round(random.uniform(58.0, 68.0), 1)
        temp_des = round(random.uniform(46.0, 52.0), 1) if is_corr else round(random.uniform(42.0, 48.0), 1)
        corr_ant = round((eq.potencia_hp or 40) * 1.32, 1)
        corr_des = round((eq.potencia_hp or 40) * 1.21, 1)

        if is_corr:
            repuestos_data = [
                {"cant": "2", "descripcion": "Rodamiento rígido de bolas 6314-2RS C3", "marca": "SKF", "codigo": "ROD-6314", "serie": f"SKF-{idx+100}", "costo": 380.0},
                {"cant": "1", "descripcion": "Retén de aceite doble labio 70x90x10", "marca": "Corteco", "codigo": "RET-7090", "serie": "N/A", "costo": 65.0}
            ]
            c_rep = 445.0
            c_mo = 250.0
            lub = "Grasa sintética Mobil Polyrex EM (160 g), solvente dieléctrico (1 gal)"
            tipos_str = "Correctivo, Reparación"
            prio = "Urgente"
            detec = "Ruido, Vibración, Temperatura"
            causa = "Desgaste normal / fin de vida útil"
            por_que = "Fin de vida útil del rodamiento tras operación continua en campaña arrocera; degradación de lubricante."
            t_parada = 3.5
        else:
            repuestos_data = [
                {"cant": "1", "descripcion": "Grasa Polyrex EM Mobil para rodamientos", "marca": "Mobil", "codigo": "LUB-POL-EM", "serie": "N/A", "costo": 85.0}
            ]
            c_rep = 85.0
            c_mo = 120.0
            lub = "Grasa Mobil Polyrex EM (120 g), solvente dieléctrico (1/2 gal)"
            tipos_str = "Preventivo, Inspección"
            prio = "Normal"
            detec = "Inspección"
            causa = "Desgaste normal / fin de vida útil"
            por_que = "Cumplimiento del plan maestro de mantenimiento preventivo para motores de Molino La Corona."
            t_parada = 1.5

        m = RegistroMantenimiento(
            equipo_id=eq.id,
            tecnico_id=tecnico.id,
            fecha=fecha_maint,
            tipo=tipo_m,
            hallazgo=hallazgo,
            validado=(random.random() > 0.15),
            observacion_encargado="Revisado y conforme por supervisión de planta." if random.random() > 0.15 else None,
            encargado_id=encargado.id if random.random() > 0.15 else None,
            numero_ot=f"OT-{idx+1:04d} / 2026",
            codigo_formato="FMT-MTO-01 | Versión 02",
            fecha_inicio=fecha_maint,
            hora_inicio="08:00",
            fecha_fin=fecha_maint,
            hora_fin="11:30" if not is_corr else "14:30",
            tiempo_parada_horas=t_parada,
            responsable_nombre="Ing. Carlos Ramírez (Jefe de Mantenimiento)",
            ejecutante_nombre="Nilser Lemuel Aguilar Silva",
            solicitado_por=f"Línea de {eq.area.capitalize()}",
            horometro=round(8200.0 + idx * 115.5, 1),
            descripcion_equipo=f"Motor trifásico {eq.nombre} ({eq.potencia_display()}) para proceso de pilado",
            marca_modelo_equipo=f"{eq.marca or 'WEG'} {eq.modelo or 'W22'}",
            numero_serie_equipo=f"{eq.codigo}-SN-{2022 + (idx % 4)}",
            tipos_trabajo=tipos_str,
            prioridad=prio,
            motivo_trabajo=hallazgo,
            sintoma_detectado=hallazgo,
            como_se_detecto=detec,
            causa_raiz=causa,
            por_que_fallo=por_que,
            trabajo_a_realizar="Inspección electromecánica, termografía, medición de vibraciones, ajuste de pernos y reengrase.",
            trabajo_realizado=hallazgo,
            vibracion_antes=vib_ant,
            vibracion_despues=vib_des,
            temperatura_antes=temp_ant,
            temperatura_despues=temp_des,
            corriente_antes=corr_ant,
            corriente_despues=corr_des,
            ruido_antes="Anormal" if is_corr else "Normal",
            ruido_despues="Normal",
            otro_parametro_nombre="Resistencia aislamiento",
            otro_parametro_unidad="MΩ",
            otro_antes="120 MΩ" if is_corr else "180 MΩ",
            otro_despues="260 MΩ",
            repuestos_json=json.dumps(repuestos_data, ensure_ascii=False),
            lubricantes_consumibles=lub,
            costo_repuestos=c_rep,
            costo_mano_obra=c_mo,
            costo_total=c_rep + c_mo,
            prueba_funcionamiento="OK",
            validado_por="Ing. Carlos Ramírez",
            fecha_proxima_intervencion=fecha_maint + timedelta(days=eq.frecuencia_mantenimiento_dias),
            recomendacion_proximo_mto="Monitoreo semanal con vibrómetro y verificación de temperatura de carcasa.",
            observaciones_fotos="Fotografías de caja de conexiones y rodamientos adjuntas en bitácora.",
            firma_ejecutante="Nilser Lemuel Aguilar Silva",
            firma_ejecutante_fecha=fecha_maint,
            firma_responsable="Ing. Carlos Ramírez",
            firma_responsable_fecha=fecha_maint,
            firma_supervisor="Ing. Supervisor de Operaciones",
            firma_supervisor_fecha=fecha_maint,
            firma_oficina="Oficina Técnica Molino La Corona",
            firma_oficina_fecha=fecha_maint,
        )
        db.session.add(m)

    # Añadir registros históricos adicionales para alimentar gráficos y auditoría
    for h_idx in range(40):
        eq_aleatorio = random.choice(equipos)
        fecha_hist = hoy - timedelta(days=random.randint(40, 360))
        t_hist = random.choice(tipos)
        h_corr = (t_hist == "correctivo")
        m_hist = RegistroMantenimiento(
            equipo_id=eq_aleatorio.id,
            tecnico_id=tecnico.id,
            fecha=fecha_hist,
            tipo=t_hist,
            hallazgo=random.choice(hallazgos_correctivos if h_corr else hallazgos_preventivos),
            validado=True,
            observacion_encargado="Mantenimiento histórico auditado según FMT-MTO-01.",
            encargado_id=encargado.id,
            numero_ot=f"OT-H{h_idx+1:03d} / 2026",
            codigo_formato="FMT-MTO-01 | Versión 02",
            fecha_inicio=fecha_hist,
            hora_inicio="08:00",
            fecha_fin=fecha_hist,
            hora_fin="12:00",
            tiempo_parada_horas=2.0,
            responsable_nombre="Ing. Carlos Ramírez (Jefe de Mantenimiento)",
            ejecutante_nombre="Nilser Lemuel Aguilar Silva",
            solicitado_por=f"Línea de {eq_aleatorio.area.capitalize()}",
            horometro=round(6500.0 + h_idx * 95.0, 1),
            descripcion_equipo=f"Motor {eq_aleatorio.nombre} ({eq_aleatorio.potencia_display()})",
            marca_modelo_equipo=f"{eq_aleatorio.marca or 'WEG'} {eq_aleatorio.modelo or 'W22'}",
            numero_serie_equipo=f"{eq_aleatorio.codigo}-SN-HIST",
            tipos_trabajo=t_hist.capitalize(),
            prioridad="Normal",
            motivo_trabajo="Intervención histórica auditada de planta.",
            sintoma_detectado="Revisión periódica de parámetros operacionales.",
            como_se_detecto="Inspección",
            causa_raiz="Desgaste normal / fin de vida útil",
            por_que_fallo="Plan de mantenimiento programado.",
            trabajo_a_realizar="Reacondicionamiento electromecánico y lubricación.",
            trabajo_realizado="Alineación, engrase de rodamientos con Polyrex EM y reapriete.",
            vibracion_antes=3.5,
            vibracion_despues=1.4,
            temperatura_antes=64.0,
            temperatura_despues=47.0,
            corriente_antes=round((eq_aleatorio.potencia_hp or 30) * 1.25, 1),
            corriente_despues=round((eq_aleatorio.potencia_hp or 30) * 1.20, 1),
            ruido_antes="Normal",
            ruido_despues="Normal",
            otro_parametro_nombre="Resistencia aislamiento",
            otro_parametro_unidad="MΩ",
            otro_antes="160 MΩ",
            otro_despues="270 MΩ",
            repuestos_json="[]",
            lubricantes_consumibles="Grasa Polyrex EM Mobil (100 g)",
            costo_repuestos=50.0,
            costo_mano_obra=100.0,
            costo_total=150.0,
            prueba_funcionamiento="OK",
            validado_por="Ing. Carlos Ramírez",
            fecha_proxima_intervencion=fecha_hist + timedelta(days=eq_aleatorio.frecuencia_mantenimiento_dias),
            recomendacion_proximo_mto="Continuar con régimen de lubricación cada 90 días.",
            observaciones_fotos="Registro histórico consolidado.",
            firma_ejecutante="Nilser Lemuel Aguilar Silva",
            firma_ejecutante_fecha=fecha_hist,
            firma_responsable="Ing. Carlos Ramírez",
            firma_responsable_fecha=fecha_hist,
            firma_supervisor="Ing. Supervisor de Operaciones",
            firma_supervisor_fecha=fecha_hist,
            firma_oficina="Oficina Técnica Molino La Corona",
            firma_oficina_fecha=fecha_hist,
        )
        db.session.add(m_hist)

    # --- CONSUMO ENERGÉTICO Y FACTURACIÓN ELÉCTRICA (MOLINO LA CORONA) ---
    # Facturación promedio de S/. 70,000 mensuales en recibos de luz.
    # Tarifa industrial promedio ~S/. 0.42 por kWh -> ~165,000 kWh/mes.
    # Pérdidas económicas por bajo factor de potencia (cos φ < 0.96) sin banco de condensadores:
    # Penalizaciones por reactiva inductiva que oscilan entre S/. 3,400 y S/. 6,800 mensuales.
    # Generamos registros mensuales del último año (12 meses):
    tarifa_kwh_soles = 0.422
    penalizaciones_mensuales = [5200.0, 4850.0, 6100.0, 3950.0, 4400.0, 5800.0, 6450.0, 4100.0, 5300.0, 4700.0, 6850.0, 5150.0]
    fp_mensuales = [0.83, 0.84, 0.81, 0.86, 0.85, 0.82, 0.81, 0.85, 0.83, 0.84, 0.80, 0.83]

    for mes_idx in range(12, 0, -1):
        fecha_recibo = hoy - timedelta(days=mes_idx * 30)
        # Consumo mensual entre 155,000 y 178,000 kWh
        kwh_mensual = round(random.uniform(158000, 175000), 1)
        penal_mes = penalizaciones_mensuales[mes_idx - 1]
        fp_mes = fp_mensuales[mes_idx - 1]

        # El importe facturado total del recibo (~S/. 70,000) ya incluye el cargo por energía reactiva
        monto_factura = round(kwh_mensual * tarifa_kwh_soles + random.uniform(-1000, 1000), 2)

        # Registro de recibo principal de Planta General
        db.session.add(
            RegistroConsumo(
                fecha=fecha_recibo,
                area="general",
                kwh=kwh_mensual,
                monto_soles=monto_factura,
                penalizacion_reactiva=penal_mes,
                factor_potencia=fp_mes,
                fuente="recibo",
                observaciones=f"Recibo mensual concesionaria. Penalización por energía reactiva aplicada (cos φ = {fp_mes:.2f} < 0.96 norma CNE/OSINERGMIN).",
                encargado_id=encargado.id,
            )
        )

        # Mediciones parciales de campo por áreas (analizador de redes portátil)
        db.session.add(
            RegistroConsumo(
                fecha=fecha_recibo - timedelta(days=12),
                area="blanqueo",
                kwh=round(kwh_mensual * 0.38, 1),  # Blanqueo consume ~38% por los motores de 80 HP
                monto_soles=round(monto_factura * 0.38, 2),
                penalizacion_reactiva=round(penal_mes * 0.42, 2),
                factor_potencia=round(max(0.78, fp_mes - 0.02), 2),
                fuente="medicion",
                observaciones="Medición de campo con analizador de redes en tablero de fuerza de motores de 80 HP (blanqueadores).",
                encargado_id=encargado.id,
            )
        )
        db.session.add(
            RegistroConsumo(
                fecha=fecha_recibo - timedelta(days=14),
                area="descascarado",
                kwh=round(kwh_mensual * 0.28, 1),
                monto_soles=round(monto_factura * 0.28, 2),
                penalizacion_reactiva=round(penal_mes * 0.30, 2),
                factor_potencia=round(min(0.87, fp_mes + 0.02), 2),
                fuente="medicion",
                observaciones="Medición de campo con analizador de redes portátil en línea de descascaradoras y extractor de cascarilla.",
                encargado_id=encargado.id,
            )
        )

    db.session.commit()
    print("Base de datos inicializada para Molino La Corona (MODO DEMO):")
    print(" - 130 motores industriales creados con potencias de hasta 80 HP.")
    print(" - Semáforo de 3 colores calibrado para defensa de tesis (Alta: Rojo, Media: Amarillo, Baja: Verde).")
    print(" - Facturación de prueba promedio de S/. 70,000/mes (~165,000 kWh/mes) y penalizaciones registradas.")
    print(" - Credenciales temporales: tecnico1 / 1234, encargado1 / 1234 (requiere cambio obligatorio al primer ingreso).")


if __name__ == "__main__":
    app = crear_app()
    with app.app_context():
        # Crear tablas mediante SQLAlchemy/Flask-Migrate
        db.create_all()

        # Verificación no destructiva de compatibilidad para columna 'debe_cambiar_password'
        try:
            import sqlite3
            db_path = os.path.join(app.instance_path, "mantenimiento.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("PRAGMA table_info(usuarios)")
                cols_u = [c[1] for c in cur.fetchall()]
                if "debe_cambiar_password" not in cols_u:
                    cur.execute("ALTER TABLE usuarios ADD COLUMN debe_cambiar_password BOOLEAN DEFAULT 0")
                    conn.commit()
                conn.close()
        except Exception:
            pass

        poblar_datos_iniciales()

    # Ejecución con debug tomado desde variables de entorno (.env)
    app.run(debug=app.config.get("DEBUG", False))
