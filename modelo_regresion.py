"""
Paso 3-4-5 del pipeline del modelo predictivo (Específico 2 y Específico 5 de la matriz de consistencia).

Tesis: Auditoría energética con modelo predictivo y sistema de gestión de mantenimiento
Molino La Corona — Tingo María, Perú
Tesista: Aguilar Silva Nilser Lemuel | FIME - UNAS

1. Ajusta una regresión lineal múltiple: EnPI = b0 + b1*X1 + b2*X2 + ... + error
2. Valida el modelo con train/test split y calcula R², RMSE y MAPE
3. Genera gráficos estadísticos para el informe de tesis (Real vs Predicho, Serie Temporal, Residuos)
4. Evalúa escenarios de mejora energética (Específico 5)
5. Exporta un reporte formal listo para ser integrado en la redacción de la tesis.
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.api as sm
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_percentage_error

from analisis_correlacion import analizar_correlacion, VARIABLE_OBJETIVO, RUTA_DATOS, BASE_DIR


def entrenar_modelo(ruta_datos: str = RUTA_DATOS, variables: list[str] | None = None):
    """
    Entrena el modelo de regresión lineal múltiple con las variables seleccionadas.
    Retorna el modelo entrenado, la lista de variables y las métricas de validación.
    """
    df = pd.read_csv(ruta_datos)
    target = VARIABLE_OBJETIVO if VARIABLE_OBJETIVO in df.columns else "enpi_kwh_eq_ton"

    if variables is None:
        tabla_corr = analizar_correlacion(ruta_datos)
        variables = tabla_corr[tabla_corr["significativa_p<0.05"]]["variable"].tolist()
        if not variables:
            print("Aviso: Ninguna variable resultó significativa con p < 0.05. Se usarán variables de producción.")
            variables = [c for c in ["ton_arroz_cascara", "ton_arroz_pilado"] if c in df.columns]

    X = df[variables]
    y = df[target]

    # División 80% entrenamiento, 20% prueba
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    X_train_const = sm.add_constant(X_train)
    modelo = sm.OLS(y_train, X_train_const).fit()

    # Validación con el conjunto de prueba
    X_test_const = sm.add_constant(X_test, has_constant="add")
    y_pred = modelo.predict(X_test_const)

    r2_test = float(r2_score(y_test, y_pred))
    rmse_test = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mape_test = float(mean_absolute_percentage_error(y_test, y_pred) * 100)

    metricas = {
        "R2_entrenamiento": float(modelo.rsquared),
        "R2_ajustado": float(modelo.rsquared_adj),
        "R2_prueba": r2_test,
        "RMSE_prueba": rmse_test,
        "MAPE_prueba_pct": mape_test,
    }

    return modelo, variables, metricas, df


def estimar_enpi(modelo, variables: list[str], valores: dict) -> float:
    """
    Estima el EnPI dado un diccionario con los valores de las variables independientes.
    """
    fila_dict = {"const": 1.0}
    for v in variables:
        fila_dict[v] = [valores.get(v, 0.0)]
    fila = pd.DataFrame(fila_dict)
    return float(modelo.predict(fila).iloc[0])


def generar_graficos_tesis(modelo, variables: list[str], df: pd.DataFrame) -> dict:
    """
    Genera gráficos de alta resolución para el cuerpo de la tesis:
    1. Real vs. Predicho (Línea Base ISO 50006)
    2. Serie Temporal de EnPI (24 meses)
    3. Análisis de Residuos
    """
    rutas_generadas = {}
    target = VARIABLE_OBJETIVO if VARIABLE_OBJETIVO in df.columns else "enpi_kwh_eq_ton"
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Predicción sobre toda la serie histórica
    X_all = sm.add_constant(df[variables])
    y_pred_all = modelo.predict(X_all)
    residuos = df[target] - y_pred_all

    # 1. Gráfico Real vs Predicho
    plt.figure(figsize=(7, 6))
    plt.scatter(df[target], y_pred_all, color="#1B3B4B", alpha=0.8, edgecolors="k", s=65, label="Meses auditados")
    min_val = min(df[target].min(), y_pred_all.min()) * 0.95
    max_val = max(df[target].max(), y_pred_all.max()) * 1.05
    plt.plot([min_val, max_val], [min_val, max_val], "r--", linewidth=2, label="Ajuste ideal (y = x)")
    plt.xlabel("EnPI Observado / Real (kWh/ton)", fontsize=11, fontweight="bold")
    plt.ylabel("EnPI Estimado por el Modelo (kWh/ton)", fontsize=11, fontweight="bold")
    plt.title(f"Línea Base Energética: EnPI Real vs. Estimado (R² = {modelo.rsquared:.3f})\nMolino La Corona (130 Motores)", fontsize=11, fontweight="bold")
    plt.legend()
    plt.tight_layout()
    ruta_real_vs_pred = os.path.join(BASE_DIR, "enpi_real_vs_predicho.png")
    plt.savefig(ruta_real_vs_pred, dpi=300)
    plt.close()
    rutas_generadas["real_vs_predicho"] = ruta_real_vs_pred

    # 2. Serie Temporal histórica de EnPI
    plt.figure(figsize=(10, 5))
    eje_x = df["mes"] if "mes" in df.columns else range(len(df))
    plt.plot(eje_x, df[target], marker="o", color="#1B3B4B", linewidth=2, label="EnPI Real (Línea Base ISO 50006)")
    plt.plot(eje_x, y_pred_all, marker="s", linestyle="--", color="#D97706", linewidth=2, label="EnPI Modelo de Regresión")
    plt.xticks(rotation=45, ha="right")
    plt.xlabel("Período (Meses Auditados)", fontsize=11, fontweight="bold")
    plt.ylabel("EnPI (kWh/ton)", fontsize=11, fontweight="bold")
    plt.title("Evolución Temporal del Indicador de Desempeño Energético (EnPI)\nPeríodo Línea Base (24 meses) — Molino La Corona", fontsize=11, fontweight="bold")
    plt.legend()
    plt.tight_layout()
    ruta_temporal = os.path.join(BASE_DIR, "linea_base_temporal.png")
    plt.savefig(ruta_temporal, dpi=300)
    plt.close()
    rutas_generadas["serie_temporal"] = ruta_temporal

    # 3. Análisis de Residuos
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    ax1.scatter(y_pred_all, residuos, color="#059669", edgecolors="k", s=50)
    ax1.axhline(0, color="red", linestyle="--", linewidth=1.5)
    ax1.set_xlabel("Valores Ajustados (kWh/ton)", fontweight="bold")
    ax1.set_ylabel("Residuos (Real - Ajustado)", fontweight="bold")
    ax1.set_title("Homocedasticidad: Residuos vs. Ajustados", fontweight="bold")

    ax2.hist(residuos, bins=8, color="#059669", edgecolor="black", alpha=0.7)
    ax2.set_xlabel("Residuo (kWh/ton)", fontweight="bold")
    ax2.set_ylabel("Frecuencia", fontweight="bold")
    ax2.set_title("Normalidad de los Errores (Histograma)", fontweight="bold")

    plt.suptitle("Diagnóstico de Residuos del Modelo de Regresión — Molino La Corona", fontsize=12, fontweight="bold")
    plt.tight_layout()
    ruta_residuos = os.path.join(BASE_DIR, "analisis_residuos.png")
    plt.savefig(ruta_residuos, dpi=300)
    plt.close()
    rutas_generadas["residuos"] = ruta_residuos

    return rutas_generadas


def exportar_resumen_tesis(modelo, variables: list[str], metricas: dict, ruta_archivo: str = os.path.join(BASE_DIR, "resumen_modelo_tesis.txt")):
    """Guarda un informe textual listo para copiar a la memoria de la tesis."""
    terminos_ecuacion = [f"{modelo.params['const']:.4f}"]
    for v in variables:
        coef = modelo.params[v]
        signo = "+" if coef >= 0 else "-"
        terminos_ecuacion.append(f"{signo} {abs(coef):.4f} * [{v}]")
    ecuacion_texto = "EnPI (kWh/ton) = " + " ".join(terminos_ecuacion)

    with open(ruta_archivo, "w", encoding="utf-8") as f:
        f.write("=" * 75 + "\n")
        f.write(" REPORTE DEL MODELO PREDICTIVO PARA LA MEMORIA DE TESIS\n")
        f.write(" Tesista: Aguilar Silva Nilser Lemuel | FIME - UNAS\n")
        f.write(" Molino La Corona — Tingo María, Perú\n")
        f.write(" Auditoría Energética de 130 Motores Eléctricos (Facturación ~S/. 70,000/mes)\n")
        f.write("=" * 75 + "\n\n")
        f.write("1. ECUACIÓN DEL MODELO DE REGRESIÓN OBTENIDA:\n")
        f.write(f"   {ecuacion_texto}\n\n")
        f.write("2. VARIABLES INDEPENDIENTES SELECCIONADAS:\n")
        for v in variables:
            f.write(f"   - {v}: coef={modelo.params[v]:.4f}, p-valor={modelo.pvalues[v]:.4e}\n")
        f.write("\n3. PARÁMETROS DE VALIDACIÓN ESTADÍSTICA (Específico 2):\n")
        f.write(f"   - Coeficiente de determinación (R² ajuste):   {metricas['R2_entrenamiento']:.4f}\n")
        f.write(f"   - Coeficiente R² ajustado:                   {metricas['R2_ajustado']:.4f}\n")
        f.write(f"   - R² en conjunto de validación (test 20%):   {metricas['R2_prueba']:.4f}\n")
        f.write(f"   - Raíz del Error Cuadrático Medio (RMSE):    {metricas['RMSE_prueba']:.4f} kWh/ton\n")
        f.write(f"   - Error Porcentual Absoluto Medio (MAPE):    {metricas['MAPE_prueba_pct']:.2f} %\n\n")
        f.write("4. TABLA ANOVA COMPLETA DE STATSMODELS:\n\n")
        f.write(str(modelo.summary()))
        f.write("\n")

    return ruta_archivo


if __name__ == "__main__":
    print("\n==================================================================")
    print(" AJUSTE Y VALIDACIÓN DEL MODELO PREDICTIVO DE CONSUMO ENERGÉTICO")
    print(" Molino La Corona — Parque de 130 Motores — Facturación S/. 70,000/mes")
    print("==================================================================")

    modelo, variables_usadas, metricas, df = entrenar_modelo()

    print(f"\nVariables incluidas en el modelo: {variables_usadas}")
    print("\nMétricas de ajuste y validación:")
    print(f"  R² Entrenamiento:  {metricas['R2_entrenamiento']:.4f}")
    print(f"  R² Ajustado:       {metricas['R2_ajustado']:.4f}")
    print(f"  R² Prueba (Test):  {metricas['R2_prueba']:.4f}")
    print(f"  RMSE Prueba:       {metricas['RMSE_prueba']:.4f} kWh/ton")
    print(f"  MAPE Prueba:       {metricas['MAPE_prueba_pct']:.2f} %")

    # --- Comparación de Escenarios (Específico 5 de la matriz de consistencia) ---
    print("\n==================================================================")
    print(" COMPARACIÓN DE ESCENARIOS OPERATIVOS (ESPECÍFICO 5)")
    print("==================================================================")

    # Valores promedio históricos como escenario base
    escenario_base = {}
    for v in variables_usadas:
        escenario_base[v] = float(df[v].mean())

    enpi_base = estimar_enpi(modelo, variables_usadas, escenario_base)
    ton_base = escenario_base.get("ton_arroz_pilado", escenario_base.get("ton_arroz_cascara", 1.0))
    consumo_base_kwh = enpi_base * ton_base
    facturacion_base_soles = consumo_base_kwh * 0.422

    print("\n1. Escenario Base (Promedios Históricos Molino La Corona):")
    for v, val in escenario_base.items():
        print(f"   - {v}: {val:.2f}")
    print(f"   -> EnPI Base Proyectado:            {enpi_base:.2f} kWh/ton")
    print(f"   -> Consumo Eléctrico Estimado:      {consumo_base_kwh:,.1f} kWh/mes")
    print(f"   -> Facturación Eléctrica Estimada:  S/. {facturacion_base_soles:,.2f} / mes")

    # Escenario de Mejora 1: Optimización de factor de carga de motores de 80 HP y balanceo (+12% volumen con igual demanda pico)
    escenario_mejora_1 = {v: val * 1.12 if "ton" in v else val for v, val in escenario_base.items()}
    enpi_mejora_1 = estimar_enpi(modelo, variables_usadas, escenario_mejora_1)
    ahorro_enpi_1 = 100 * (enpi_base - enpi_mejora_1) / enpi_base
    ahorro_soles = (enpi_base - enpi_mejora_1) * ton_base * 0.422

    print("\n2. Escenario con Mejora (Optimización de Carga en Motores de 80 HP y Gestión Preventiva):")
    for v, val in escenario_mejora_1.items():
        print(f"   - {v}: {val:.2f}")
    print(f"   -> EnPI Mejorado:                   {enpi_mejora_1:.2f} kWh/ton")
    print(f"   -> Reducción relativa EnPI:         {ahorro_enpi_1:.2f} % de ahorro específico")
    print(f"   -> Ahorro Económico Proyectado:     S/. {ahorro_soles:,.2f} / mes")

    # Generar gráficos y reporte
    graficos = generar_graficos_tesis(modelo, variables_usadas, df)
    print("\nGráficos de tesis generados:")
    for k, ruta in graficos.items():
        print(f"  [{k}] -> {ruta}")

    reporte = exportar_resumen_tesis(modelo, variables_usadas, metricas)
    print(f"\nReporte formal de regresión exportado a:\n  -> {reporte}")
