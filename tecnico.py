import json
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from extensions import db
from models import Equipo, RegistroMantenimiento, ROL_TECNICO
from decoradores import requiere_rol

tecnico_bp = Blueprint("tecnico", __name__, url_prefix="/tecnico")


def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


@tecnico_bp.route("/registrar", methods=["GET", "POST"])
@login_required
@requiere_rol(ROL_TECNICO)
def registrar():
    """
    El técnico registra intervenciones en el parque de 130 motores de Molino La Corona
    utilizando el formato oficial FMT-MTO-01 Versión 02 (OT - Orden de Trabajo).
    """
    equipos = Equipo.query.order_by(Equipo.codigo).all()

    # Calcular sugerencia de siguiente N.° de Orden de Trabajo
    ultimo = RegistroMantenimiento.query.order_by(RegistroMantenimiento.id.desc()).first()
    siguiente_id = (ultimo.id + 1) if ultimo else 1
    ot_sugerida = f"OT-{siguiente_id:04d} / 2026"

    if request.method == "POST":
        equipo_id_raw = request.form.get("equipo_id")
        if not equipo_id_raw:
            flash("Debe seleccionar un motor del parque de Molino La Corona.", "danger")
            return redirect(url_for("tecnico.registrar"))

        try:
            equipo_id = int(equipo_id_raw)
            equipo = Equipo.query.get_or_404(equipo_id)
        except ValueError:
            flash("Identificador de equipo inválido.", "danger")
            return redirect(url_for("tecnico.registrar"))

        # Encabezado
        numero_ot = request.form.get("numero_ot", "").strip() or ot_sugerida
        codigo_formato = request.form.get("codigo_formato", "FMT-MTO-01 | Versión 02").strip()

        # 1. Datos Generales
        fecha_inicio = parse_date(request.form.get("fecha_inicio")) or date.today()
        hora_inicio = request.form.get("hora_inicio", "08:00").strip()
        fecha_fin = parse_date(request.form.get("fecha_fin")) or fecha_inicio
        hora_fin = request.form.get("hora_fin", "12:00").strip()
        try:
            tiempo_parada_horas = float(request.form.get("tiempo_parada_horas") or 0.0)
        except ValueError:
            tiempo_parada_horas = 0.0

        responsable_nombre = request.form.get("responsable_nombre", "").strip() or None
        ejecutante_nombre = request.form.get("ejecutante_nombre", "").strip() or current_user.nombre_completo
        solicitado_por = request.form.get("solicitado_por", "").strip() or None

        # 2. Datos del Equipo
        try:
            horometro = float(request.form.get("horometro")) if request.form.get("horometro") else None
        except ValueError:
            horometro = None

        descripcion_equipo = request.form.get("descripcion_equipo", "").strip() or equipo.nombre
        marca_modelo_form = request.form.get("marca_modelo_equipo", "").strip()
        if marca_modelo_form:
            marca_modelo_equipo = marca_modelo_form
        elif equipo.marca or equipo.modelo:
            marca_modelo_equipo = f"{equipo.marca or ''} {equipo.modelo or ''}".strip() or None
        else:
            marca_modelo_equipo = None

        numero_serie_equipo = request.form.get("numero_serie_equipo", "").strip() or None

        # 3. Tipo de Trabajo
        tipos_trabajo_list = request.form.getlist("tipos_trabajo")
        tipos_trabajo = ", ".join(tipos_trabajo_list) if tipos_trabajo_list else "Preventivo"
        prioridad = request.form.get("prioridad", "Normal").strip()

        # 4. Falla, Motivo y Causa Raíz
        motivo_trabajo = request.form.get("motivo_trabajo", "").strip()
        sintoma_detectado = request.form.get("sintoma_detectado", "").strip()
        como_se_detecto_list = request.form.getlist("como_se_detecto")
        como_se_detecto = ", ".join(como_se_detecto_list)
        causa_raiz_list = request.form.getlist("causa_raiz")
        causa_raiz = ", ".join(causa_raiz_list)
        por_que_fallo = request.form.get("por_que_fallo", "").strip()

        # 5. Trabajo
        trabajo_a_realizar = request.form.get("trabajo_a_realizar", "").strip()
        trabajo_realizado = request.form.get("trabajo_realizado", "").strip()

        # 6. Mediciones Antes y Después
        def parse_float_field(key):
            val = request.form.get(key, "").strip()
            if not val:
                return None
            try:
                return float(val)
            except ValueError:
                return None

        vibracion_antes = parse_float_field("vibracion_antes")
        vibracion_despues = parse_float_field("vibracion_despues")
        temperatura_antes = parse_float_field("temperatura_antes")
        temperatura_despues = parse_float_field("temperatura_despues")
        corriente_antes = parse_float_field("corriente_antes")
        corriente_despues = parse_float_field("corriente_despues")
        ruido_antes = request.form.get("ruido_antes", "Normal").strip()
        ruido_despues = request.form.get("ruido_despues", "Normal").strip()
        otro_parametro_nombre = request.form.get("otro_parametro_nombre", "").strip()
        otro_parametro_unidad = request.form.get("otro_parametro_unidad", "").strip()
        otro_antes = request.form.get("otro_antes", "").strip()
        otro_despues = request.form.get("otro_despues", "").strip()

        # 7. Piezas, Repuestos y Materiales
        cants = request.form.getlist("repuesto_cant[]")
        descs = request.form.getlist("repuesto_desc[]")
        marcas = request.form.getlist("repuesto_marca[]")
        cods = request.form.getlist("repuesto_codigo[]")
        series = request.form.getlist("repuesto_serie[]")
        costos = request.form.getlist("repuesto_costo[]")

        repuestos_lista = []
        suma_repuestos = 0.0
        for i in range(len(descs)):
            desc = descs[i].strip() if i < len(descs) else ""
            if desc:
                cant_str = cants[i].strip() if i < len(cants) else "1"
                mrc_str = marcas[i].strip() if i < len(marcas) else ""
                cod_str = cods[i].strip() if i < len(cods) else ""
                ser_str = series[i].strip() if i < len(series) else ""
                cost_flt = 0.0
                if i < len(costos) and costos[i].strip():
                    try:
                        cost_flt = float(costos[i].strip())
                    except ValueError:
                        cost_flt = 0.0
                suma_repuestos += cost_flt
                repuestos_lista.append({
                    "cant": cant_str,
                    "descripcion": desc,
                    "marca": mrc_str,
                    "codigo": cod_str,
                    "serie": ser_str,
                    "costo": cost_flt,
                })

        lubricantes_consumibles = request.form.get("lubricantes_consumibles", "").strip()

        try:
            costo_repuestos = float(request.form.get("costo_repuestos") or suma_repuestos)
        except ValueError:
            costo_repuestos = suma_repuestos

        try:
            costo_mano_obra = float(request.form.get("costo_mano_obra") or 0.0)
        except ValueError:
            costo_mano_obra = 0.0

        try:
            costo_total = float(request.form.get("costo_total") or (costo_repuestos + costo_mano_obra))
        except ValueError:
            costo_total = costo_repuestos + costo_mano_obra

        # 8. Cierre y Seguimiento
        prueba_funcionamiento = request.form.get("prueba_funcionamiento", "OK").strip()
        validado_por = request.form.get("validado_por", "").strip()
        fecha_proxima_intervencion = parse_date(request.form.get("fecha_proxima_intervencion"))
        recomendacion_proximo_mto = request.form.get("recomendacion_proximo_mto", "").strip()
        observaciones_fotos = request.form.get("observaciones_fotos", "").strip()

        # 9. Firmas y Validación
        firma_ejecutante = request.form.get("firma_ejecutante", "").strip() or current_user.nombre_completo
        firma_ejecutante_fecha = parse_date(request.form.get("firma_ejecutante_fecha")) or fecha_inicio
        firma_responsable = request.form.get("firma_responsable", "").strip()
        firma_responsable_fecha = parse_date(request.form.get("firma_responsable_fecha"))
        firma_supervisor = request.form.get("firma_supervisor", "").strip()
        firma_supervisor_fecha = parse_date(request.form.get("firma_supervisor_fecha"))
        firma_oficina = request.form.get("firma_oficina", "").strip()
        firma_oficina_fecha = parse_date(request.form.get("firma_oficina_fecha"))

        # Campos legacy / compatibilidad
        tipo_legacy = "correctivo" if ("Correctivo" in tipos_trabajo or "Reparación" in tipos_trabajo) else "preventivo"
        hallazgo_legacy = trabajo_realizado or motivo_trabajo or "Mantenimiento según FMT-MTO-01"

        nuevo_registro = RegistroMantenimiento(
            equipo_id=equipo_id,
            tecnico_id=current_user.id,
            fecha=fecha_inicio,
            tipo=tipo_legacy,
            hallazgo=hallazgo_legacy,
            numero_ot=numero_ot,
            codigo_formato=codigo_formato,
            fecha_inicio=fecha_inicio,
            hora_inicio=hora_inicio,
            fecha_fin=fecha_fin,
            hora_fin=hora_fin,
            tiempo_parada_horas=tiempo_parada_horas,
            responsable_nombre=responsable_nombre,
            ejecutante_nombre=ejecutante_nombre,
            solicitado_por=solicitado_por,
            horometro=horometro,
            descripcion_equipo=descripcion_equipo,
            marca_modelo_equipo=marca_modelo_equipo,
            numero_serie_equipo=numero_serie_equipo,
            tipos_trabajo=tipos_trabajo,
            prioridad=prioridad,
            motivo_trabajo=motivo_trabajo,
            sintoma_detectado=sintoma_detectado,
            como_se_detecto=como_se_detecto,
            causa_raiz=causa_raiz,
            por_que_fallo=por_que_fallo,
            trabajo_a_realizar=trabajo_a_realizar,
            trabajo_realizado=trabajo_realizado,
            vibracion_antes=vibracion_antes,
            vibracion_despues=vibracion_despues,
            temperatura_antes=temperatura_antes,
            temperatura_despues=temperatura_despues,
            corriente_antes=corriente_antes,
            corriente_despues=corriente_despues,
            ruido_antes=ruido_antes,
            ruido_despues=ruido_despues,
            otro_parametro_nombre=otro_parametro_nombre,
            otro_parametro_unidad=otro_parametro_unidad,
            otro_antes=otro_antes,
            otro_despues=otro_despues,
            repuestos_json=json.dumps(repuestos_lista, ensure_ascii=False),
            lubricantes_consumibles=lubricantes_consumibles,
            costo_repuestos=costo_repuestos,
            costo_mano_obra=costo_mano_obra,
            costo_total=costo_total,
            prueba_funcionamiento=prueba_funcionamiento,
            validado_por=validado_por,
            fecha_proxima_intervencion=fecha_proxima_intervencion,
            recomendacion_proximo_mto=recomendacion_proximo_mto,
            observaciones_fotos=observaciones_fotos,
            firma_ejecutante=firma_ejecutante,
            firma_ejecutante_fecha=firma_ejecutante_fecha,
            firma_responsable=firma_responsable,
            firma_responsable_fecha=firma_responsable_fecha,
            firma_supervisor=firma_supervisor,
            firma_supervisor_fecha=firma_supervisor_fecha,
            firma_oficina=firma_oficina,
            firma_oficina_fecha=firma_oficina_fecha,
            validado=False,
        )

        db.session.add(nuevo_registro)
        db.session.commit()

        flash(f"Orden de Trabajo {nuevo_registro.codigo_ot()} guardada con éxito según formato oficial FMT-MTO-01.", "success")
        return redirect(url_for("tecnico.ver_ot", registro_id=nuevo_registro.id))

    return render_template(
        "registrar_mantenimiento.html",
        equipos=equipos,
        ot_sugerida=ot_sugerida,
        hoy=date.today().isoformat()
    )


@tecnico_bp.route("/ot/<int:registro_id>")
@login_required
@requiere_rol(ROL_TECNICO)
def ver_ot(registro_id):
    """Visualización e impresión oficial de la Orden de Trabajo FMT-MTO-01 Versión 02."""
    registro = RegistroMantenimiento.query.get_or_404(registro_id)
    return render_template("orden_trabajo_ver.html", registro=registro)


@tecnico_bp.route("/historial")
@login_required
@requiere_rol(ROL_TECNICO)
def historial():
    """El técnico puede CONSULTAR, pero no editar, sus propios registros."""
    mis_registros = (
        RegistroMantenimiento.query.filter_by(tecnico_id=current_user.id)
        .order_by(RegistroMantenimiento.fecha.desc())
        .all()
    )
    return render_template("historial_tecnico.html", registros=mis_registros)


@tecnico_bp.route("/equipos")
@login_required
@requiere_rol(ROL_TECNICO)
def ver_equipos():
    """Consulta de solo lectura de las fichas técnicas de los 130 motores con semáforo de 3 colores."""
    todos = Equipo.query.order_by(Equipo.codigo).all()

    conteo_total = len(todos)
    conteo_alta = sum(1 for e in todos if e.nivel_urgencia() == "alta")
    conteo_media = sum(1 for e in todos if e.nivel_urgencia() == "media")
    conteo_baja = sum(1 for e in todos if e.nivel_urgencia() == "baja")

    filtro_urgencia = request.args.get("urgencia", "").strip().lower()
    filtro_area = request.args.get("area", "").strip().lower()
    busqueda = request.args.get("q", "").strip().lower()

    equipos_filtrados = todos

    if filtro_urgencia in ["alta", "media", "baja"]:
        equipos_filtrados = [e for e in equipos_filtrados if e.nivel_urgencia() == filtro_urgencia]

    if filtro_area:
        equipos_filtrados = [e for e in equipos_filtrados if e.area == filtro_area]

    if busqueda:
        equipos_filtrados = [
            e for e in equipos_filtrados
            if busqueda in (e.nombre or "").lower()
            or busqueda in (e.codigo or "").lower()
            or busqueda in (e.marca or "").lower()
            or busqueda in f"{e.potencia_hp or ''} hp".lower()
        ]

    return render_template(
        "equipos_lista_tecnico.html",
        equipos=equipos_filtrados,
        conteo_total=conteo_total,
        conteo_alta=conteo_alta,
        conteo_media=conteo_media,
        conteo_baja=conteo_baja,
        filtro_urgencia=filtro_urgencia,
        filtro_area=filtro_area,
        busqueda=busqueda,
    )
