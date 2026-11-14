from datetime import date, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

# Roles posibles del sistema (Específico 3 de la matriz de consistencia)
ROL_TECNICO = "tecnico"
ROL_ENCARGADO = "encargado"


class Usuario(db.Model, UserMixin):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre_completo = db.Column(db.String(120), nullable=False)
    nombres = db.Column(db.String(80), nullable=True)
    apellidos = db.Column(db.String(80), nullable=True)
    codigo_institucional = db.Column(db.String(30), nullable=True)  # Ej: '0020220644' o 'TEC-0084'
    cargo = db.Column(db.String(120), nullable=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False)  # ROL_TECNICO o ROL_ENCARGADO
    debe_cambiar_password = db.Column(db.Boolean, default=False, nullable=False)  # Forzar cambio de contraseña inicial (1234)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def es_encargado(self) -> bool:
        return self.rol == ROL_ENCARGADO

    def obtener_nombres(self) -> str:
        """Retorna los nombres en mayúsculas (ej: 'NILSER LEMUEL')."""
        if self.nombres:
            return self.nombres.strip().upper()
        partes = self.nombre_completo.strip().split()
        if len(partes) >= 2:
            return " ".join(partes[:2]).upper()
        return self.nombre_completo.strip().upper()

    def obtener_apellidos(self) -> str:
        """Retorna los apellidos en mayúsculas (ej: 'AGUILAR SILVA')."""
        if self.apellidos:
            return self.apellidos.strip().upper()
        partes = self.nombre_completo.strip().split()
        if len(partes) > 2:
            return " ".join(partes[2:]).upper()
        elif len(partes) == 2:
            return partes[1].strip().upper()
        return ""

    def texto_badge(self) -> str:
        """Texto para la píldora turquesa (ej: 'Alumno 0020220644' o 'Técnico TEC-0084')."""
        if self.codigo_institucional:
            if "00202" in self.codigo_institucional or self.rol == ROL_ENCARGADO:
                return f"Alumno {self.codigo_institucional}"
            elif "TEC" in self.codigo_institucional:
                return f"Técnico {self.codigo_institucional}"
            return f"Código {self.codigo_institucional}"
        return f"{self.rol.capitalize()} Molino"


class Equipo(db.Model):
    __tablename__ = "equipos"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), nullable=True)  # Ej: 'M-001', 'M-080'
    nombre = db.Column(db.String(120), nullable=False)
    area = db.Column(db.String(50), nullable=False)  # 'blanqueo', 'descascarado', 'secado', 'prelimpieza', 'clasificacion'
    frecuencia_mantenimiento_dias = db.Column(db.Integer, nullable=False, default=90)

    # Ficha técnica de motores (Molino La Corona: 130 motores de hasta 80 HP)
    marca = db.Column(db.String(80), nullable=True)  # WEG, Siemens, ABB, Delcrosa, etc.
    modelo = db.Column(db.String(80), nullable=True)
    potencia_hp = db.Column(db.Float, nullable=True)  # Potencia en HP (ej: 80.0, 50.0)
    potencia_kw = db.Column(db.Float, nullable=True)  # Potencia en kW (1 HP ≈ 0.7457 kW)
    anio_instalacion = db.Column(db.Integer, nullable=True)
    horas_uso_dia = db.Column(db.Float, nullable=True)

    registros = db.relationship("RegistroMantenimiento", backref="equipo", lazy=True)

    def proxima_fecha_sugerida(self):
        ultimo = (
            RegistroMantenimiento.query.filter_by(equipo_id=self.id)
            .order_by(RegistroMantenimiento.fecha.desc())
            .first()
        )
        if not ultimo:
            # Si aún no tiene mantenimientos registrados, se calcula desde el inicio de año o se asume hoy
            return date.today()
        return ultimo.fecha + timedelta(days=self.frecuencia_mantenimiento_dias)

    def dias_restantes(self) -> int:
        """
        Retorna la cantidad de días restantes para el próximo mantenimiento.
        Valores negativos indican días de retraso / vencimiento.
        """
        proxima = self.proxima_fecha_sugerida()
        if proxima is None:
            return 0
        return (proxima - date.today()).days

    def esta_vencido(self) -> bool:
        return self.dias_restantes() <= 0

    # -----------------------------------------------------------------------
    # Semáforo de 3 Colores según Urgencia de Mantenimiento de Motores
    # -----------------------------------------------------------------------
    def nivel_urgencia(self) -> str:
        """
        Clasifica el motor en 3 niveles de urgencia:
          - 'alta'    (ROJO): Mantenimiento vencido (<= 0 días) o correctivo urgente.
          - 'media'   (AMARILLO): Próximo a vencer dentro de los próximos 15 días.
          - 'baja'    (VERDE): Al día, más de 15 días restantes.
        """
        dias = self.dias_restantes()
        if dias <= 0:
            return "alta"
        elif dias <= 15:
            return "media"
        else:
            return "baja"

    def color_urgencia(self) -> str:
        """Retorna la clase Bootstrap correspondiente al semáforo de 3 colores."""
        niveles = {
            "alta": "danger",     # Rojo
            "media": "warning",   # Amarillo / Ámbar
            "baja": "success",    # Verde
        }
        return niveles.get(self.nivel_urgencia(), "secondary")

    def etiqueta_urgencia(self) -> str:
        """Texto formal de la urgencia para reportes y tablas."""
        etiquetas = {
            "alta": "Alta (Vencido)",
            "media": "Media (Próximo)",
            "baja": "Baja (Al Día)",
        }
        return etiquetas.get(self.nivel_urgencia(), "Normal")

    def potencia_display(self) -> str:
        """Presentación combinada de HP y kW para la ficha técnica del motor."""
        if self.potencia_hp and self.potencia_kw:
            return f"{self.potencia_hp:g} HP ({self.potencia_kw:.1f} kW)"
        elif self.potencia_hp:
            return f"{self.potencia_hp:g} HP"
        elif self.potencia_kw:
            return f"{self.potencia_kw:.1f} kW"
        return "—"


class RegistroConsumo(db.Model):
    """
    Consumo energético mensual o diario (Línea Base Energética ISO 50001).
    Adaptado a Molino La Corona con facturación promedio de ~S/. 70,000 mensuales.
    Incluye monitoreo de energía reactiva y factor de potencia para dimensionamiento
    y justificación del banco de condensadores.
    """

    __tablename__ = "registros_consumo"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    area = db.Column(db.String(50), nullable=False, default="general")  # 'general', 'blanqueo', 'descascarado', 'secado', 'prelimpieza', 'clasificacion'
    kwh = db.Column(db.Float, nullable=False)
    monto_soles = db.Column(db.Float, nullable=True)  # Importe facturado total en Soles (promedio ~S/. 70,000 / mes)
    
    # --- Nuevos campos de Gestión Energética & Reactiva (Tesis FIME - UNAS) ---
    penalizacion_reactiva = db.Column(db.Float, nullable=False, default=0.0)  # Penalización por energía reactiva en S/.
    factor_potencia = db.Column(db.Float, nullable=True, default=0.85)  # Factor de potencia registrado (cos φ, meta >= 0.96)
    fuente = db.Column(db.String(20), nullable=False, default="recibo")  # 'recibo' o 'medicion'
    observaciones = db.Column(db.Text, nullable=True)  # Observaciones operativas, N° recibo o analizador de redes
    
    encargado_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    def monto_sin_penalizacion(self) -> float:
        """Importe facturado neto excluyendo la penalización por energía reactiva."""
        total = self.monto_soles if self.monto_soles is not None else round(self.kwh * 0.422, 2)
        penalizacion = self.penalizacion_reactiva or 0.0
        return max(0.0, total - penalizacion)

    def estado_factor_potencia(self) -> str:
        """
        Evalúa el factor de potencia respecto a la Norma Técnica de Calidad
        de los Servicios Eléctricos del Perú (OSINERGMIN / CNE):
          - 'optimo': FP >= 0.96 (Sin penalización)
          - 'regular': 0.90 <= FP < 0.96 (Próximo al límite regulatorio)
          - 'critico': FP < 0.90 (Penalización severa por reactiva inductiva)
        """
        if self.factor_potencia is None:
            return "desconocido"
        if self.factor_potencia >= 0.96:
            return "optimo"
        elif self.factor_potencia >= 0.90:
            return "regular"
        return "critico"

    def badge_factor_potencia(self) -> str:
        """Retorna la clase CSS de Bootstrap para representar el estado del FP."""
        estados = {
            "optimo": "bg-success",
            "regular": "bg-warning text-dark",
            "critico": "bg-danger",
            "desconocido": "bg-secondary",
        }
        return estados.get(self.estado_factor_potencia(), "bg-secondary")


class RegistroMantenimiento(db.Model):
    """
    Formato oficial de Orden de Trabajo (OT) para Molino La Corona:
    'FORMATO DE MANTENIMIENTO DE EQUIPOS Y/O MOTORES — Molino arrocero – Registro de mantenimiento'
    Código: FMT-MTO-01 | Versión 02
    """
    __tablename__ = "registros_mantenimiento"

    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    tipo = db.Column(db.String(50), nullable=False, default="preventivo")  # 'preventivo', 'correctivo', etc.
    hallazgo = db.Column(db.Text, nullable=False)

    # Solo el encargado puede llenar/editar estos dos campos:
    validado = db.Column(db.Boolean, nullable=False, default=False)
    observacion_encargado = db.Column(db.Text, nullable=True)
    encargado_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)

    # --- ENCABEZADO FMT-MTO-01 Versión 02 ---
    numero_ot = db.Column(db.String(40), nullable=True)  # Ej: 'OT-0001 / 2026'
    codigo_formato = db.Column(db.String(50), nullable=False, default="FMT-MTO-01 | Versión 02")

    # 1. DATOS GENERALES
    fecha_inicio = db.Column(db.Date, nullable=True, default=date.today)
    hora_inicio = db.Column(db.String(10), nullable=True, default="08:00")
    fecha_fin = db.Column(db.Date, nullable=True, default=date.today)
    hora_fin = db.Column(db.String(10), nullable=True, default="12:00")
    tiempo_parada_horas = db.Column(db.Float, nullable=True, default=0.0)
    responsable_nombre = db.Column(db.String(120), nullable=True)
    ejecutante_nombre = db.Column(db.String(120), nullable=True)
    solicitado_por = db.Column(db.String(120), nullable=True)

    # 2. DATOS DEL EQUIPO (detalles de ficha de campo)
    horometro = db.Column(db.Float, nullable=True)
    descripcion_equipo = db.Column(db.Text, nullable=True)
    marca_modelo_equipo = db.Column(db.String(120), nullable=True)
    numero_serie_equipo = db.Column(db.String(80), nullable=True)

    # 3. TIPO DE TRABAJO
    tipos_trabajo = db.Column(db.String(255), nullable=True, default="Preventivo")  # Predictivo, Preventivo, Correctivo, Inspección, Reparación
    prioridad = db.Column(db.String(20), nullable=True, default="Normal")  # Urgente, Normal, Programable

    # 4. FALLA, MOTIVO Y CAUSA RAÍZ
    motivo_trabajo = db.Column(db.Text, nullable=True)
    sintoma_detectado = db.Column(db.Text, nullable=True)
    como_se_detecto = db.Column(db.String(255), nullable=True)  # Ruido, Vibración, Temperatura, Inspección, Operador, Otro
    causa_raiz = db.Column(db.String(255), nullable=True)  # Falta lubricación, Exceso grasa, Desalineamiento, Sobrecarga, Contaminación, Desgaste, Mala instalación, Otro
    por_que_fallo = db.Column(db.Text, nullable=True)  # Explicar la causa real

    # 5. TRABAJO
    trabajo_a_realizar = db.Column(db.Text, nullable=True)
    trabajo_realizado = db.Column(db.Text, nullable=True)

    # 6. MEDICIONES ANTES Y DESPUÉS
    vibracion_antes = db.Column(db.Float, nullable=True)
    vibracion_despues = db.Column(db.Float, nullable=True)
    temperatura_antes = db.Column(db.Float, nullable=True)
    temperatura_despues = db.Column(db.Float, nullable=True)
    corriente_antes = db.Column(db.Float, nullable=True)
    corriente_despues = db.Column(db.Float, nullable=True)
    ruido_antes = db.Column(db.String(20), nullable=True, default="Normal")  # Normal / Anormal
    ruido_despues = db.Column(db.String(20), nullable=True, default="Normal")
    otro_parametro_nombre = db.Column(db.String(80), nullable=True)
    otro_parametro_unidad = db.Column(db.String(30), nullable=True)
    otro_antes = db.Column(db.String(50), nullable=True)
    otro_despues = db.Column(db.String(50), nullable=True)

    # 7. PIEZAS, REPUESTOS Y MATERIALES UTILIZADOS
    repuestos_json = db.Column(db.Text, nullable=True, default="[]")  # Lista JSON: [{cant, descripcion, marca, codigo, serie, costo}]
    lubricantes_consumibles = db.Column(db.Text, nullable=True)  # Tipo de grasa/aceite y cantidad
    costo_repuestos = db.Column(db.Float, nullable=True, default=0.0)
    costo_mano_obra = db.Column(db.Float, nullable=True, default=0.0)
    costo_total = db.Column(db.Float, nullable=True, default=0.0)

    # 8. CIERRE Y SEGUIMIENTO
    prueba_funcionamiento = db.Column(db.String(20), nullable=True, default="OK")  # OK / No OK
    validado_por = db.Column(db.String(120), nullable=True)
    fecha_proxima_intervencion = db.Column(db.Date, nullable=True)
    recomendacion_proximo_mto = db.Column(db.Text, nullable=True)
    observaciones_fotos = db.Column(db.Text, nullable=True)

    # 9. FIRMAS Y VALIDACIÓN
    firma_ejecutante = db.Column(db.String(120), nullable=True)
    firma_ejecutante_fecha = db.Column(db.Date, nullable=True)
    firma_responsable = db.Column(db.String(120), nullable=True)
    firma_responsable_fecha = db.Column(db.Date, nullable=True)
    firma_supervisor = db.Column(db.String(120), nullable=True)
    firma_supervisor_fecha = db.Column(db.Date, nullable=True)
    firma_oficina = db.Column(db.String(120), nullable=True)
    firma_oficina_fecha = db.Column(db.Date, nullable=True)

    tecnico = db.relationship("Usuario", foreign_keys=[tecnico_id])
    encargado = db.relationship("Usuario", foreign_keys=[encargado_id])

    def codigo_ot(self) -> str:
        """Retorna el código formal de la Orden de Trabajo (ej: 'OT-0012 / 2026')."""
        if self.numero_ot and self.numero_ot.strip():
            return self.numero_ot
        return f"OT-{self.id:04d} / 2026"

    def lista_tipos_trabajo(self) -> list:
        if not self.tipos_trabajo:
            return [self.tipo.capitalize()] if self.tipo else []
        return [t.strip() for t in self.tipos_trabajo.split(",") if t.strip()]

    def lista_como_se_detecto(self) -> list:
        if not self.como_se_detecto:
            return []
        return [c.strip() for c in self.como_se_detecto.split(",") if c.strip()]

    def lista_causa_raiz(self) -> list:
        if not self.causa_raiz:
            return []
        return [c.strip() for c in self.causa_raiz.split(",") if c.strip()]

    def lista_repuestos(self) -> list:
        import json
        if not self.repuestos_json:
            return []
        try:
            items = json.loads(self.repuestos_json)
            if isinstance(items, list):
                return items
            return []
        except Exception:
            return []
