"""
Servicio del Modelo Predictivo de Consumo Energético (EnPI).
Conecta el Específico 2 (Modelo Predictivo) con el Específico 3 (Sistema Web).
Molino La Corona — Tingo María, Perú
Tesista: Aguilar Silva Nilser Lemuel | FIME - UNAS
"""

import os
import sys
import pandas as pd
import numpy as np
import statsmodels.api as sm

# Ruta al directorio modelo_predictivo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELO_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "modelo_predictivo"))
RUTA_DATOS = os.path.join(MODELO_DIR, "datos_simulados.csv")

_CACHE_MODELO = None
_CACHE_METRICAS = None
_CACHE_DATOS = None


def inicializar_modelo():
    global _CACHE_MODELO, _CACHE_METRICAS, _CACHE_DATOS
    if _CACHE_MODELO is not None:
        return _CACHE_MODELO, _CACHE_METRICAS, _CACHE_DATOS

    if not os.path.exists(RUTA_DATOS):
        return None, None, None

    df = pd.read_csv(RUTA_DATOS)

    # Identificar variables del proceso de pilado de arroz en Molino La Corona
    if "ton_arroz_cascara" in df.columns:
        var_cascara = "ton_arroz_cascara"
        var_pilado = "ton_arroz_pilado"
        var_enpi = "enpi_kwh_ton" if "enpi_kwh_ton" in df.columns else "enpi_kwh_eq_ton"
    else:
        var_cascara = "ton_cacao"
        var_pilado = "ton_cafe"
        var_enpi = "enpi_kwh_eq_ton"

    variables = [var_cascara, var_pilado]

    X = df[variables]
    y = df[var_enpi]
    X_const = sm.add_constant(X)
    modelo = sm.OLS(y, X_const).fit()

    # Predicciones y métricas
    y_pred = modelo.predict(X_const)
    r2 = float(modelo.rsquared)
    r2_adj = float(modelo.rsquared_adj)
    rmse = float(np.sqrt(np.mean((y - y_pred) ** 2)))
    mape = float(np.mean(np.abs((y - y_pred) / y)) * 100)

    # Coeficientes
    b0 = float(modelo.params["const"])
    b_cascara = float(modelo.params[var_cascara])
    b_pilado = float(modelo.params[var_pilado])

    promedio_cascara = float(df[var_cascara].mean())
    promedio_pilado = float(df[var_pilado].mean())
    promedio_enpi = float(df[var_enpi].mean())
    promedio_consumo = float(df["consumo_electrico_kwh"].mean())
    promedio_facturacion = float(df["facturacion_soles"].mean()) if "facturacion_soles" in df.columns else round(promedio_consumo * 0.422, 2)

    promedio_penalizacion = 5160.0  # Promedio de penalizaciones por reactiva inductiva (S/. 5,160/mes)
    promedio_fp = 0.83  # Factor de potencia promedio histórico sin compensación
    # Tarifa activa pura (sin componente de penalización por reactiva)
    tarifa_activa_pura = round((promedio_facturacion - promedio_penalizacion) / promedio_consumo, 4) if promedio_consumo > 0 else 0.3908

    _CACHE_MODELO = modelo
    _CACHE_DATOS = df
    _CACHE_METRICAS = {
        "r2": round(r2, 4),
        "r2_adj": round(r2_adj, 4),
        "rmse": round(rmse, 3),
        "mape": round(mape, 2),
        "b0": round(b0, 4),
        "b_cascara": round(b_cascara, 4),
        "b_pilado": round(b_pilado, 4),
        "prom_arroz_cascara": round(promedio_cascara, 1),
        "prom_arroz_pilado": round(promedio_pilado, 1),
        "prom_cacao": round(promedio_cascara, 1),  # retrocompatibilidad
        "prom_cafe": round(promedio_pilado, 1),   # retrocompatibilidad
        "prom_enpi": round(promedio_enpi, 2),
        "prom_consumo": round(promedio_consumo, 1),
        "prom_facturacion_soles": round(promedio_facturacion, 2),
        "prom_penalizacion_reactiva": round(promedio_penalizacion, 2),
        "prom_factor_potencia": round(promedio_fp, 2),
        "tarifa_activa_pura": round(tarifa_activa_pura, 4),
        "tarifa_total_con_reactiva": 0.422,
        "formula": f"EnPI = {b0:.2f} {b_cascara:+.4f}*(Ton. Arroz Cáscara) {b_pilado:+.4f}*(Ton. Arroz Pilado)",
    }

    return _CACHE_MODELO, _CACHE_METRICAS, _CACHE_DATOS


def obtener_penalizacion_promedio_bd() -> float:
    """Consulta la penalización por reactiva promedio real registrada en la base de datos."""
    try:
        from models import RegistroConsumo
        from sqlalchemy import func
        from extensions import db
        prom = (
            db.session.query(func.avg(RegistroConsumo.penalizacion_reactiva))
            .filter(RegistroConsumo.area == "general", RegistroConsumo.penalizacion_reactiva > 0)
            .scalar()
        )
        if prom and prom > 0:
            return round(float(prom), 2)
    except Exception:
        pass
    return 5160.0


def obtener_metricas_modelo():
    _, metricas, _ = inicializar_modelo()
    if metricas:
        metricas["prom_penalizacion_reactiva"] = obtener_penalizacion_promedio_bd()
    return metricas


def simular_produccion(ton_arroz_cascara: float, ton_arroz_pilado: float, penalizacion_referencia: float | None = None) -> dict:
    """
    Calcula el EnPI proyectado, el consumo de los 130 motores y el impacto económico
    en la facturación mensual de Molino La Corona.
    
    Implementa los requisitos de la tesis:
    - Arroz cáscara procesado en toneladas/mes
    - Arroz pilado obtenido en toneladas/mes
    - Consumo específico estimado: kWh por tonelada procesada (EnPI)
    - Consumo proyectado en kWh/mes según volumen de producción
    - Facturación proyectada en S/ — calculada YA SIN incluir penalizaciones por reactiva
    - Ahorro estimado mensual = monto de penalizaciones que dejan de pagarse
    """
    modelo, metricas, df = inicializar_modelo()
    if modelo is None:
        return {"error": "No se encontraron los datos del modelo predictivo."}

    var_cascara = "ton_arroz_cascara" if "ton_arroz_cascara" in df.columns else "ton_cacao"
    var_pilado = "ton_arroz_pilado" if "ton_arroz_pilado" in df.columns else "ton_cafe"

    fila = pd.DataFrame({"const": [1.0], var_cascara: [ton_arroz_cascara], var_pilado: [ton_arroz_pilado]})
    enpi_estimado = float(modelo.predict(fila).iloc[0])

    ton_total = ton_arroz_cascara  # base arroz cáscara procesado
    rendimiento_pilado_pct = round((ton_arroz_pilado / ton_arroz_cascara) * 100, 2) if ton_arroz_cascara > 0 else 69.0
    consumo_estimado_kwh = enpi_estimado * (ton_arroz_pilado if ton_arroz_pilado > 0 else ton_total * 0.69)

    # Tarifa de energía activa pura (sin recargo de reactiva inductiva)
    tarifa_activa_pura = metricas.get("tarifa_activa_pura", 0.3908)
    # Facturación proyectada en S/ — calculada YA SIN incluir penalizaciones por reactiva
    facturacion_proyectada_sin_reactiva = round(consumo_estimado_kwh * tarifa_activa_pura, 2)

    # Facturación que se pagaría bajo el régimen actual CON penalizaciones (tarifa completa ~0.422)
    tarifa_actual_con_multas = 0.422
    facturacion_con_penalizacion = round(consumo_estimado_kwh * tarifa_actual_con_multas, 2)

    # Penalización mensual de reactiva que se elimina con el banco de condensadores
    if penalizacion_referencia is not None and penalizacion_referencia >= 0:
        penalizacion_mensual_evitada = round(float(penalizacion_referencia), 2)
    else:
        penalizacion_mensual_evitada = round(obtener_penalizacion_promedio_bd(), 2)

    # Ahorro estimado mensual por eliminación directa de penalizaciones
    ahorro_penalizacion_mensual = penalizacion_mensual_evitada
    ahorro_penalizacion_anual = round(ahorro_penalizacion_mensual * 12, 2)

    # Comparación con la línea base histórica
    enpi_base = metricas["prom_enpi"]
    diferencia_enpi = enpi_estimado - enpi_base
    variacion_enpi_pct = ((enpi_estimado - enpi_base) / enpi_base) * 100 if enpi_base > 0 else 0.0

    # Ahorro adicional por eficiencia operativa en motores (si EnPI proyectado < EnPI base)
    es_ahorro_eficiencia = variacion_enpi_pct < 0
    kwh_base_referencia = enpi_base * (ton_arroz_pilado if ton_arroz_pilado > 0 else ton_total * 0.69)
    ahorro_eficiencia_soles = round(max(0.0, (kwh_base_referencia - consumo_estimado_kwh) * tarifa_activa_pura), 2) if es_ahorro_eficiencia else 0.0

    # Ahorro total integral (Penalizaciones reactivas que dejan de pagarse + mejora de eficiencia EnPI)
    ahorro_total_mensual = round(ahorro_penalizacion_mensual + ahorro_eficiencia_soles, 2)
    ahorro_total_anual = round(ahorro_total_mensual * 12, 2)

    # Estimación de amortización del banco de condensadores trifásico automático (~120 kVAR / S/. 28,500)
    costo_inversion_banco = 28500.0
    meses_recuperacion = round(costo_inversion_banco / ahorro_penalizacion_mensual, 1) if ahorro_penalizacion_mensual > 0 else 0.0

    return {
        "ton_arroz_cascara": ton_arroz_cascara,
        "ton_arroz_pilado": ton_arroz_pilado,
        "ton_total": round(ton_total, 1),
        "rendimiento_pilado_pct": rendimiento_pilado_pct,
        # Consumo específico estimado: kWh por tonelada procesada
        "consumo_especifico_estimado": round(enpi_estimado, 2),
        "enpi_estimado": round(enpi_estimado, 2),
        # Consumo proyectado en kWh/mes según volumen de producción
        "consumo_proyectado_kwh": round(consumo_estimado_kwh, 1),
        "consumo_estimado_kwh": round(consumo_estimado_kwh, 1),
        # Facturación proyectada en S/ — calculada YA SIN incluir penalizaciones por reactiva
        "facturacion_proyectada_sin_reactiva": facturacion_proyectada_sin_reactiva,
        "facturacion_estimada_soles": facturacion_proyectada_sin_reactiva,
        "facturacion_con_penalizacion": facturacion_con_penalizacion,
        # Ahorro mensual = monto de penalizaciones que dejan de pagarse
        "ahorro_estimado_mensual": ahorro_penalizacion_mensual,
        "ahorro_soles_mes": ahorro_total_mensual,
        "ahorro_penalizacion_mensual": ahorro_penalizacion_mensual,
        "ahorro_penalizacion_anual": ahorro_penalizacion_anual,
        "ahorro_eficiencia_soles": ahorro_eficiencia_soles,
        "ahorro_total_mensual": ahorro_total_mensual,
        "ahorro_total_anual": ahorro_total_anual,
        "penalizacion_mensual_evitada": penalizacion_mensual_evitada,
        # Indicadores de retorno y línea base
        "enpi_base": enpi_base,
        "variacion_pct": round(abs(variacion_enpi_pct), 2),
        "es_ahorro": es_ahorro_eficiencia,
        "tarifa_activa_pura": tarifa_activa_pura,
        "costo_inversion_banco": costo_inversion_banco,
        "meses_recuperacion": meses_recuperacion,
        "formula": metricas["formula"],
    }
