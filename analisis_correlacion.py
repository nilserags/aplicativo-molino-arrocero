"""
Paso 1-2 del pipeline del modelo predictivo (Específico 2 de la matriz de consistencia).

Tesis: Auditoría energética con modelo predictivo y sistema de gestión de mantenimiento
Molino La Corona — Tingo María, Perú
Tesista: Aguilar Silva Nilser Lemuel | FIME - UNAS

Lee los datos de proceso del pilado de arroz y el consumo específico de energía (EnPI),
calcula la correlación de Pearson con significancia estadística (p < 0.05)
y genera la matriz visual de correlaciones para el informe de tesis.
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_DATOS = os.path.join(BASE_DIR, "datos_simulados.csv")
VARIABLE_OBJETIVO = "enpi_kwh_ton"

VARIABLES_CANDIDATAS = [
    "ton_arroz_cascara",
    "ton_arroz_pilado",
    "humedad_paddy_pct",
    "horas_molienda",
    "temperatura_secado_C",
]


def analizar_correlacion(ruta_datos: str = RUTA_DATOS) -> pd.DataFrame:
    """Calcula coeficientes de correlación de Pearson y p-valores contra el EnPI."""
    df = pd.read_csv(ruta_datos)

    target = VARIABLE_OBJETIVO if VARIABLE_OBJETIVO in df.columns else "enpi_kwh_eq_ton"
    vars_disponibles = [v for v in VARIABLES_CANDIDATAS if v in df.columns]

    resultados = []
    for variable in vars_disponibles:
        r, p_valor = pearsonr(df[variable], df[target])
        resultados.append(
            {
                "variable": variable,
                "correlacion_pearson_r": round(float(r), 3),
                "p_valor": round(float(p_valor), 4),
                "significativa_p<0.05": bool(p_valor < 0.05),
            }
        )

    resultados_df = pd.DataFrame(resultados).sort_values(
        by="correlacion_pearson_r", key=abs, ascending=False
    )
    return resultados_df


def graficar_matriz_correlacion(
    ruta_datos: str = RUTA_DATOS,
    ruta_guardar: str = os.path.join(BASE_DIR, "matriz_correlacion.png"),
) -> str:
    """Genera y guarda el mapa de calor (heatmap) de correlaciones para la tesis."""
    df = pd.read_csv(ruta_datos)
    target = VARIABLE_OBJETIVO if VARIABLE_OBJETIVO in df.columns else "enpi_kwh_eq_ton"
    vars_disponibles = [v for v in VARIABLES_CANDIDATAS if v in df.columns]
    cols = vars_disponibles + [target]
    corr = df[cols].corr(method="pearson")

    nombres_legibles = {
        "ton_arroz_cascara": "Ton. Arroz Cáscara",
        "ton_arroz_pilado": "Ton. Arroz Pilado",
        "humedad_paddy_pct": "Humedad Paddy (%)",
        "horas_molienda": "Horas Molienda (h)",
        "temperatura_secado_C": "Temp. Secado (°C)",
        "enpi_kwh_ton": "EnPI (kWh/ton)",
        "enpi_kwh_eq_ton": "EnPI (kWh/ton)",
    }
    corr.rename(index=nombres_legibles, columns=nombres_legibles, inplace=True)

    plt.figure(figsize=(9, 7))
    sns.set_theme(style="white")
    cmap = sns.diverging_palette(220, 20, as_cmap=True)

    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap=cmap,
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        linewidths=0.5,
        cbar_kws={"shrink": 0.8, "label": "Coeficiente de Pearson (r)"},
    )

    plt.title(
        "Matriz de Correlación de Pearson - Variables de Proceso vs. EnPI\nMolino La Corona (Parque de 130 Motores)",
        fontsize=12,
        fontweight="bold",
        pad=15,
    )
    plt.tight_layout()
    plt.savefig(ruta_guardar, dpi=300)
    plt.close()
    return ruta_guardar


if __name__ == "__main__":
    tabla = analizar_correlacion()
    print("\n==================================================================")
    print(" ANÁLISIS DE CORRELACIÓN DE PEARSON - AUDITORÍA ENERGÉTICA MOLINO LA CORONA")
    print("==================================================================")
    print(tabla.to_string(index=False))

    seleccionadas = tabla[tabla["significativa_p<0.05"]]["variable"].tolist()
    print(f"\nVariables estadísticamente significativas (p < 0.05): {seleccionadas}")
    print("Estas variables son las seleccionadas para el modelo de regresión (Específico 2).")

    img_path = graficar_matriz_correlacion()
    print(f"\nGráfico de matriz de correlación guardado exitosamente en:\n -> {img_path}")
