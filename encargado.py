import csv
import io
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models import Equipo, RegistroMantenimiento, RegistroConsumo, ROL_ENCARGADO
from decoradores import requiere_rol
from servicio_predictivo import obtener_metricas_modelo, simular_produccion

encargado_bp = Blueprint("encargado", __name__, url_prefix="/encargado")


@encargado_bp.route("/dashboard")
@login_required
@requiere_rol(ROL_ENCARGADO)
def dashboard():
    """Vista central en la sala de cómputo de Molino La Corona con KPIs y semáforo de 3 colores."""
    registros = RegistroMantenimiento.query.order_by(
        RegistroMantenimiento.fecha.desc()
    ).all()
    equipos = Equipo.query.order_by(Equipo.codigo).all()

    # Clasificación en el semáforo de 3 colores de urgencia
    motores_alta = [e for e in equipos if e.nivel_urgencia() == "alta"]
    motores_media = [e for e in equipos if e.nivel_urgencia() == "media"]
    motores_baja = [e for e in equipos if e.nivel_urgencia() == "baja"]

    consumo_total = db.session.query(func.sum(RegistroConsumo.kwh)).scalar() or 0.0
    facturacion_total = db.session.query(func.sum(RegistroConsumo.monto_soles)).scalar() or 0.0

    # Promedio mensual de recibos de luz en Planta General
    promedio_facturacion = (
        db.session.query(func.avg(RegistroConsumo.monto_soles))
        .filter(RegistroConsumo.area == "general", RegistroConsumo.fuente == "recibo")
        .scalar()
    ) or 70000.0

    # Pérdidas acumuladas y promedio mensual por penalizaciones de energía reactiva
    penalizacion_total = (
        db.session.query(func.sum(RegistroConsumo.penalizacion_reactiva))
        .filter(RegistroConsumo.area == "general")
        .scalar()
    ) or 0.0

    promedio_penalizacion = (
        db.session.query(func.avg(RegistroConsumo.penalizacion_reactiva))
        .filter(RegistroConsumo.area == "general", RegistroConsumo.penalizacion_reactiva > 0)
        .scalar()
    ) or 5160.0

    promedio_fp = (
        db.session.query(func.avg(RegistroConsumo.factor_potencia))
        .filter(RegistroConsumo.area == "general", RegistroConsumo.factor_potencia.isnot(None))
        .scalar()
    ) or 0.83

    # Indicadores Clave (KPIs)
    kpis = {
        "total_equipos": len(equipos),
        "motores_alta": len(motores_alta),      # 🔴 Urgencia Alta
        "motores_media": len(motores_media),    # 🟡 Urgencia Media
        "motores_baja": len(motores_baja),      # 🟢 Urgencia Baja
        "equipos_vencidos": len(motores_alta),
        "equipos_proximos": len(motores_media),
        "total_mantenimientos": len(registros),
        "pendientes_validacion": sum(1 for r in registros if not r.validado),
        "consumo_total_kwh": round(consumo_total, 1),
        "facturacion_total_soles": round(facturacion_total, 2),
        "facturacion_promedio_mensual": round(promedio_facturacion, 2),
        "penalizacion_total_soles": round(penalizacion_total, 2),
        "penalizacion_promedio_mensual": round(promedio_penalizacion, 2),
        "factor_potencia_promedio": round(promedio_fp, 2),
        "ahorro_anual_proyectado": round(promedio_penalizacion * 12, 2),
    }

    # Datos mensuales para las gráficas principales del Dashboard (estilo Rocker)
    filas_consumo = (
        db.session.query(
            func.strftime("%Y-%m", RegistroConsumo.fecha).label("mes"),
            func.sum(RegistroConsumo.kwh).label("kwh_total"),
            func.sum(RegistroConsumo.monto_soles).label("soles_total"),
        )
        .group_by("mes")
        .order_by("mes")
        .all()
    )
    chart_consumo = {
        "labels": [f[0] for f in filas_consumo] if filas_consumo else ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"],
        "kwh": [round(f[1], 1) for f in filas_consumo] if filas_consumo else [158000, 162000, 168000, 164000, 170000, 166000, 172000, 169000, 165000, 171000, 167000, 165000],
        "soles": [round(f[2] or (f[1] * 0.422), 2) for f in filas_consumo] if filas_consumo else [66676, 68364, 70896, 69208, 71740, 70052, 72584, 71318, 69630, 72162, 70474, 69630],
    }

    filas_mto = (
        db.session.query(
            func.strftime("%Y-%m", RegistroMantenimiento.fecha).label("mes"),
            func.count(RegistroMantenimiento.id).label("cantidad"),
        )
        .group_by("mes")
        .order_by("mes")
        .all()
    )
    chart_mantenimiento = {
        "labels": [f[0] for f in filas_mto] if filas_mto else ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"],
        "valores": [f[1] for f in filas_mto] if filas_mto else [8, 12, 15, 10, 14, 9, 11, 16, 13, 15, 12, 14],
    }

    return render_template(
        "dashboard_encargado.html",
        registros=registros,
        equipos_vencidos=motores_alta,
        equipos_proximos=motores_media,
        kpis=kpis,
        chart_consumo=chart_consumo,
        chart_mantenimiento=chart_mantenimiento,
    )


@encargado_bp.route("/validar/<int:registro_id>", methods=["GET", "POST"])
@login_required
@requiere_rol(ROL_ENCARGADO)
def validar(registro_id):
    """
    Único punto del sistema donde se puede EDITAR un registro ya creado.
    Solo accesible por el rol encargado (protegido por @requiere_rol).
    Permite validar la Orden de Trabajo según el formato oficial FMT-MTO-01 Versión 02.
    """
    registro = RegistroMantenimiento.query.get_or_404(registro_id)

    if request.method == "POST":
        registro.observacion_encargado = request.form.get("observacion_encargado", "").strip()
        registro.validado = True
        registro.encargado_id = current_user.id

        # Campos de cierre del formato FMT-MTO-01
        if request.form.get("prueba_funcionamiento"):
            registro.prueba_funcionamiento = request.form.get("prueba_funcionamiento").strip()
        if request.form.get("validado_por"):
            registro.validado_por = request.form.get("validado_por").strip()
        else:
            registro.validado_por = current_user.nombre_completo

        if request.form.get("recomendacion_proximo_mto"):
            registro.recomendacion_proximo_mto = request.form.get("recomendacion_proximo_mto").strip()

        fecha_prox_str = request.form.get("fecha_proxima_intervencion")
        if fecha_prox_str:
            try:
                registro.fecha_proxima_intervencion = datetime.strptime(fecha_prox_str.strip(), "%Y-%m-%d").date()
            except Exception:
                pass

        # Firmas de supervisión y oficina
        registro.firma_supervisor = request.form.get("firma_supervisor", "").strip() or current_user.nombre_completo
        registro.firma_supervisor_fecha = date.today()
        if request.form.get("firma_oficina"):
            registro.firma_oficina = request.form.get("firma_oficina").strip()
            registro.firma_oficina_fecha = date.today()

        db.session.commit()
        flash(f"Orden de Trabajo {registro.codigo_ot()} validada y firmada con éxito en Molino La Corona.", "success")
        return redirect(url_for("encargado.dashboard"))

    return render_template("validar_registro.html", registro=registro)


@encargado_bp.route("/ot/<int:registro_id>")
@login_required
@requiere_rol(ROL_ENCARGADO)
def ver_ot(registro_id):
    """Visualización e impresión oficial de la Orden de Trabajo FMT-MTO-01 Versión 02 para el encargado."""
    registro = RegistroMantenimiento.query.get_or_404(registro_id)
    return render_template("orden_trabajo_ver.html", registro=registro)


# ---------------------------------------------------------------------------
# Fichas técnicas de motores (Inventario de 130 motores, potencias en HP y semáforo)
# ---------------------------------------------------------------------------

@encargado_bp.route("/equipos")
@login_required
@requiere_rol(ROL_ENCARGADO)
def listar_equipos():
    """Listado completo del parque de 130 motores con filtrado por semáforo de 3 colores y área."""
    todos = Equipo.query.order_by(Equipo.codigo).all()

    # Conteos para los botones del semáforo
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
            or busqueda in (e.modelo or "").lower()
            or busqueda in f"{e.potencia_hp or ''} hp".lower()
        ]

    return render_template(
        "equipos_lista.html",
        equipos=equipos_filtrados,
        conteo_total=conteo_total,
        conteo_alta=conteo_alta,
        conteo_media=conteo_media,
        conteo_baja=conteo_baja,
        filtro_urgencia=filtro_urgencia,
        filtro_area=filtro_area,
        busqueda=busqueda,
    )


@encargado_bp.route("/equipos/<int:equipo_id>/editar", methods=["GET", "POST"])
@login_required
@requiere_rol(ROL_ENCARGADO)
def editar_equipo(equipo_id):
    """Solo el encargado puede crear/editar la ficha técnica de un motor."""
    equipo = Equipo.query.get_or_404(equipo_id)

    if request.method == "POST":
        try:
            equipo.codigo = request.form.get("codigo") or equipo.codigo
            equipo.nombre = request.form.get("nombre") or equipo.nombre
            equipo.area = request.form.get("area") or equipo.area
            equipo.marca = request.form.get("marca") or None
            equipo.modelo = request.form.get("modelo") or None

            hp_val = request.form.get("potencia_hp")
            if hp_val:
                equipo.potencia_hp = float(hp_val)
                # Auto-calcular kW si no se especificó
                kw_val = request.form.get("potencia_kw")
                equipo.potencia_kw = float(kw_val) if kw_val else round(equipo.potencia_hp * 0.7457, 1)
            else:
                kw_val = request.form.get("potencia_kw")
                equipo.potencia_kw = float(kw_val) if kw_val else None

            equipo.anio_instalacion = int(request.form["anio_instalacion"]) if request.form.get("anio_instalacion") else None
            equipo.horas_uso_dia = float(request.form["horas_uso_dia"]) if request.form.get("horas_uso_dia") else None
            equipo.frecuencia_mantenimiento_dias = int(request.form.get("frecuencia_mantenimiento_dias", 90))

            db.session.commit()
            flash(f"Ficha técnica del motor {equipo.codigo} ({equipo.nombre}) actualizada con éxito.", "success")
            return redirect(url_for("encargado.listar_equipos"))
        except (ValueError, KeyError) as e:
            flash(f"Error en los datos ingresados: {e}", "danger")

    return render_template("equipo_editar.html", equipo=equipo)


# ---------------------------------------------------------------------------
# Registro de consumo energético (Línea base — Facturación de luz ~S/. 70,000)
# ---------------------------------------------------------------------------

@encargado_bp.route("/consumo", methods=["GET", "POST"])
@login_required
@requiere_rol(ROL_ENCARGADO)
def registrar_consumo():
    if request.method == "POST":
        try:
            fecha_val = datetime.strptime(request.form["fecha"], "%Y-%m-%d").date()
            kwh_val = float(request.form["kwh"])

            # Importe facturado en soles (o cálculo a tarifa industrial de ~0.422 S//kWh)
            monto_soles_raw = request.form.get("monto_soles")
            if monto_soles_raw and float(monto_soles_raw) > 0:
                monto_soles_val = float(monto_soles_raw)
            else:
                monto_soles_val = round(kwh_val * 0.422, 2)

            penalizacion_raw = request.form.get("penalizacion_reactiva")
            penalizacion_val = float(penalizacion_raw) if penalizacion_raw and float(penalizacion_raw) >= 0 else 0.0

            fp_raw = request.form.get("factor_potencia")
            fp_val = float(fp_raw) if fp_raw and fp_raw.strip() else None

            observaciones_val = request.form.get("observaciones", "").strip() or None

            nuevo = RegistroConsumo(
                fecha=fecha_val,
                area=request.form.get("area", "general"),
                kwh=kwh_val,
                monto_soles=monto_soles_val,
                penalizacion_reactiva=penalizacion_val,
                factor_potencia=fp_val,
                fuente=request.form.get("fuente", "recibo"),
                observaciones=observaciones_val,
                encargado_id=current_user.id,
            )
            db.session.add(nuevo)
            db.session.commit()

            msg_fp = f" | FP: {fp_val:.2f}" if fp_val is not None else ""
            msg_penal = f" | Penalización Reactiva: S/. {penalizacion_val:,.2f}" if penalizacion_val > 0 else " | Sin penalización reactiva"
            flash(f"Lectura registrada con éxito: {kwh_val:,.1f} kWh (Total: S/. {monto_soles_val:,.2f}{msg_penal}{msg_fp}) en Molino La Corona.", "success")
            return redirect(url_for("encargado.registrar_consumo"))
        except (ValueError, KeyError) as e:
            flash(f"Error en los datos ingresados: {e}. Verifique los valores ingresados.", "danger")

    ultimos = RegistroConsumo.query.order_by(RegistroConsumo.fecha.desc()).limit(20).all()
    return render_template("registrar_consumo.html", ultimos=ultimos)


# ---------------------------------------------------------------------------
# Módulo Predictivo y Simulador EnPI (Específico 2 & 5) — Molino La Corona
# ---------------------------------------------------------------------------

@encargado_bp.route("/simulador-enpi", methods=["GET", "POST"])
@login_required
@requiere_rol(ROL_ENCARGADO)
def simulador_enpi():
    """Simulador interactivo de desempeño energético (EnPI) y ahorro con banco de condensadores."""
    metricas = obtener_metricas_modelo()
    resultado_simulacion = None

    if request.method == "POST":
        try:
            ton_arroz_cascara = float(request.form.get("ton_arroz_cascara", request.form.get("ton_cacao", 0)))
            ton_arroz_pilado = float(request.form.get("ton_arroz_pilado", request.form.get("ton_cafe", 0)))
            penalizacion_referencia_raw = request.form.get("penalizacion_referencia")
            penalizacion_ref = float(penalizacion_referencia_raw) if penalizacion_referencia_raw and float(penalizacion_referencia_raw) >= 0 else None
            resultado_simulacion = simular_produccion(ton_arroz_cascara, ton_arroz_pilado, penalizacion_ref)
        except ValueError:
            flash("Ingrese valores numéricos válidos para la simulación.", "danger")

    return render_template(
        "simulador_enpi.html",
        metricas=metricas,
        resultado=resultado_simulacion,
    )


# ---------------------------------------------------------------------------
# Gráficas (HTML + Chart.js consumen estos endpoints JSON)
# ---------------------------------------------------------------------------

@encargado_bp.route("/graficos")
@login_required
@requiere_rol(ROL_ENCARGADO)
def graficos():
    return render_template("graficos.html")


@encargado_bp.route("/api/consumo-mensual")
@login_required
@requiere_rol(ROL_ENCARGADO)
def api_consumo_mensual():
    filas = (
        db.session.query(
            func.strftime("%Y-%m", RegistroConsumo.fecha).label("mes"),
            func.sum(RegistroConsumo.kwh).label("kwh_total"),
            func.sum(RegistroConsumo.monto_soles).label("soles_total"),
            func.sum(RegistroConsumo.penalizacion_reactiva).label("penalizacion_total"),
            func.avg(RegistroConsumo.factor_potencia).label("fp_promedio"),
        )
        .group_by("mes")
        .order_by("mes")
        .all()
    )
    labels = [f[0] for f in filas]
    valores = [round(f[1], 1) for f in filas]
    soles = [round(f[2] or (f[1] * 0.422), 2) for f in filas]
    penalizaciones = [round(f[3] or 0.0, 2) for f in filas]
    soles_sin_reactiva = [round(max(0.0, (f[2] or (f[1] * 0.422)) - (f[3] or 0.0)), 2) for f in filas]
    fps = [round(f[4] or 0.83, 2) for f in filas]
    meta_penalizacion = [0.0 for _ in filas]
    meta_fp = [0.96 for _ in filas]

    return jsonify({
        "labels": labels,
        "valores": valores,
        "soles": soles,
        "penalizacion_reactiva": penalizaciones,
        "soles_sin_reactiva": soles_sin_reactiva,
        "factor_potencia": fps,
        "meta_penalizacion": meta_penalizacion,
        "meta_fp": meta_fp,
    })


@encargado_bp.route("/api/penalizaciones-reactiva")
@login_required
@requiere_rol(ROL_ENCARGADO)
def api_penalizaciones_reactiva():
    """
    Datos exclusivos para la gráfica de penalizaciones por energía reactiva:
    - Curva de datos: montos cobrados mes a mes (fluctuaciones reales en S/.)
    - Línea meta fija: 0 S/. (objetivo con banco de condensadores)
    - Dinero que se recupera mes a mes y acumulado
    """
    filas = (
        db.session.query(
            func.strftime("%Y-%m", RegistroConsumo.fecha).label("mes"),
            func.sum(RegistroConsumo.penalizacion_reactiva).label("penalizacion_total"),
            func.avg(RegistroConsumo.factor_potencia).label("fp_promedio"),
            func.sum(RegistroConsumo.monto_soles).label("factura_total"),
        )
        .group_by("mes")
        .order_by("mes")
        .all()
    )

    labels = [f[0] for f in filas]
    penalizaciones = [round(f[1] or 0.0, 2) for f in filas]
    meta_fija = [0.0 for _ in filas]
    fps = [round(f[2] or 0.83, 2) for f in filas]

    # Dinero recuperable acumulado mes a mes
    acumulado = []
    total_acum = 0.0
    for p in penalizaciones:
        total_acum += p
        acumulado.append(round(total_acum, 2))

    total_cobrado = sum(penalizaciones)
    promedio_mensual = round(total_cobrado / len(penalizaciones), 2) if penalizaciones else 0.0

    return jsonify({
        "labels": labels,
        "penalizaciones": penalizaciones,
        "meta_fija": meta_fija,
        "factor_potencia": fps,
        "acumulado_recuperable": acumulado,
        "kpis": {
            "total_penalizaciones": round(total_cobrado, 2),
            "promedio_mensual": promedio_mensual,
            "ahorro_anual_proyectado": round(promedio_mensual * 12, 2),
            "fp_promedio": round(sum(fps) / len(fps), 2) if fps else 0.83,
        }
    })


@encargado_bp.route("/api/consumo-diario")
@login_required
@requiere_rol(ROL_ENCARGADO)
def api_consumo_diario():
    filas = (
        db.session.query(RegistroConsumo.fecha, RegistroConsumo.kwh, RegistroConsumo.monto_soles, RegistroConsumo.penalizacion_reactiva)
        .order_by(RegistroConsumo.fecha)
        .all()
    )
    return jsonify({
        "labels": [f[0].isoformat() for f in filas],
        "valores": [f[1] for f in filas],
        "soles": [f[2] or round(f[1] * 0.422, 2) for f in filas],
        "penalizaciones": [round(f[3] or 0.0, 2) for f in filas],
    })


@encargado_bp.route("/api/mantenimientos-por-mes")
@login_required
@requiere_rol(ROL_ENCARGADO)
def api_mantenimientos_por_mes():
    filas = (
        db.session.query(
            func.strftime("%Y-%m", RegistroMantenimiento.fecha).label("mes"),
            func.count(RegistroMantenimiento.id).label("cantidad"),
        )
        .group_by("mes")
        .order_by("mes")
        .all()
    )
    return jsonify({"labels": [f[0] for f in filas], "valores": [f[1] for f in filas]})


@encargado_bp.route("/api/mantenimientos-por-dia")
@login_required
@requiere_rol(ROL_ENCARGADO)
def api_mantenimientos_por_dia():
    """En qué día del mes se concentran los mantenimientos (1 al 31)."""
    filas = (
        db.session.query(
            func.strftime("%d", RegistroMantenimiento.fecha).label("dia"),
            func.count(RegistroMantenimiento.id).label("cantidad"),
        )
        .group_by("dia")
        .order_by("dia")
        .all()
    )
    return jsonify({"labels": [f[0] for f in filas], "valores": [f[1] for f in filas]})


# ---------------------------------------------------------------------------
# Exportación de datos a CSV (para anexos del informe de tesis)
# ---------------------------------------------------------------------------

@encargado_bp.route("/exportar/mantenimientos")
@login_required
@requiere_rol(ROL_ENCARGADO)
def exportar_mantenimientos():
    """Exporta el historial completo de órdenes de trabajo FMT-MTO-01 en formato CSV para Excel y tesis."""
    registros = RegistroMantenimiento.query.order_by(RegistroMantenimiento.fecha.desc()).all()

    output = io.StringIO()
    # BOM UTF-8 para apertura correcta con tildes en Excel
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow([
        "ID", "N.° Orden Trabajo (OT)", "Código Formato", "Fecha", "Código Motor", "Nombre Motor", "Potencia", "Área Molino",
        "Técnico Ejecutante", "Responsable", "Tipo Mantenimiento", "Prioridad", "Semáforo Urgencia",
        "Horómetro (h)", "Tiempo Parada (h)", "Motivo del Trabajo", "Síntoma Detectado", "¿Cómo se Detectó?",
        "Causa Raíz", "¿Por qué Falló?", "Trabajo Realizado",
        "Vibración Antes (mm/s)", "Vibración Después (mm/s)",
        "Temperatura Antes (°C)", "Temperatura Después (°C)",
        "Corriente Antes (A)", "Corriente Después (A)",
        "Ruido Antes", "Ruido Después", "Lubricantes / Consumibles",
        "Costo Repuestos S/", "Costo Mano Obra S/", "Costo Total S/",
        "Prueba Funcionamiento", "Validado por", "Fecha Próx. Intervención",
        "Recomendación Próximo Mantenimiento", "Validado", "Observación Encargado"
    ])

    for r in registros:
        eq = r.equipo
        writer.writerow([
            r.id,
            r.codigo_ot(),
            r.codigo_formato or "FMT-MTO-01 | Versión 02",
            r.fecha.isoformat() if r.fecha else "",
            eq.codigo if eq else (r.numero_serie_equipo or ""),
            eq.nombre if eq else (r.descripcion_equipo or ""),
            eq.potencia_display() if eq else "",
            eq.area.capitalize() if eq else "",
            r.ejecutante_nombre or (r.tecnico.nombre_completo if r.tecnico else ""),
            r.responsable_nombre or "",
            r.tipos_trabajo or (r.tipo.capitalize() if r.tipo else ""),
            r.prioridad or "Normal",
            eq.etiqueta_urgencia() if eq else "",
            r.horometro if r.horometro is not None else "",
            r.tiempo_parada_horas if r.tiempo_parada_horas is not None else "",
            r.motivo_trabajo or "",
            r.sintoma_detectado or "",
            r.como_se_detecto or "",
            r.causa_raiz or "",
            r.por_que_fallo or "",
            r.trabajo_realizado or r.hallazgo or "",
            r.vibracion_antes if r.vibracion_antes is not None else "",
            r.vibracion_despues if r.vibracion_despues is not None else "",
            r.temperatura_antes if r.temperatura_antes is not None else "",
            r.temperatura_despues if r.temperatura_despues is not None else "",
            r.corriente_antes if r.corriente_antes is not None else "",
            r.corriente_despues if r.corriente_despues is not None else "",
            r.ruido_antes or "",
            r.ruido_despues or "",
            r.lubricantes_consumibles or "",
            f"{r.costo_repuestos:.2f}" if r.costo_repuestos is not None else "0.00",
            f"{r.costo_mano_obra:.2f}" if r.costo_mano_obra is not None else "0.00",
            f"{r.costo_total:.2f}" if r.costo_total is not None else "0.00",
            r.prueba_funcionamiento or "OK",
            r.validado_por or "",
            r.fecha_proxima_intervencion.isoformat() if r.fecha_proxima_intervencion else "",
            r.recomendacion_proximo_mto or "",
            "Sí" if r.validado else "No",
            r.observacion_encargado or "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=historial_ordenes_trabajo_molino_la_corona.csv"}
    )


@encargado_bp.route("/exportar/consumo")
@login_required
@requiere_rol(ROL_ENCARGADO)
def exportar_consumo():
    """Exporta los registros de consumo energético, facturación y reactiva de Molino La Corona en CSV."""
    consumos = RegistroConsumo.query.order_by(RegistroConsumo.fecha.desc()).all()

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Fecha", "Área Molino", "Consumo (kWh)", "Facturación Total (S/.)",
        "Facturación Sin Reactiva (S/.)", "Penalización Reactiva (S/.)",
        "Factor de Potencia (FP)", "Estado FP", "Fuente de Medición", "Observaciones"
    ])

    for c in consumos:
        factura_total = c.monto_soles or round(c.kwh * 0.422, 2)
        factura_sin_penal = c.monto_sin_penalizacion()
        writer.writerow([
            c.id,
            c.fecha.isoformat(),
            c.area.capitalize(),
            round(c.kwh, 1),
            round(factura_total, 2),
            round(factura_sin_penal, 2),
            round(c.penalizacion_reactiva or 0.0, 2),
            f"{c.factor_potencia:.2f}" if c.factor_potencia is not None else "",
            c.estado_factor_potencia().capitalize(),
            "Recibo Concesionaria" if c.fuente == "recibo" else "Medición de Campo",
            c.observaciones or "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=registro_consumo_molino_la_corona.csv"}
    )
