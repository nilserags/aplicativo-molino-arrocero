# Proyecto de tesis — Auditoría energética con modelo predictivo y sistema de gestión de mantenimiento

**Molino La Corona — Tingo María, Perú**  
**Tesista:** Aguilar Silva Nilser Lemuel | FIME - UNAS (Facultad de Ingeniería Mecánica y Eléctrica)  
**Contexto Operativo:** Planta de molienda y pilado de arroz con un parque de **130 motores eléctricos** (tamaños variados hasta **80 HP**) y una facturación eléctrica promedio de **S/. 70,000 mensuales** (~165,000 kWh/mes).

---

## Novedades y Adecuaciones al Nuevo Contexto

1. **Parque de 130 Motores Eléctricos:**
   - Inventario industrial categorizado por áreas de proceso: *Blanqueo y Pulido*, *Descascarado y Separación Paddy*, *Secado y Silos*, *Tolvas y Prelimpieza*, y *Clasificación y Ensacado*.
   - Motores de gran potencia destacados (**80 HP**, 75 HP, 60 HP, 50 HP) y motores intermedios/pequeños (40 HP a 3 HP).
   - Fichas técnicas con potencia en HP y kW ($1\text{ HP} \approx 0.7457\text{ kW}$).

2. **Semáforo de 3 Colores según Urgencia de Mantenimiento:**
   - 🔴 **Urgencia Alta (Rojo):** Motores con frecuencia de mantenimiento vencida ($\le 0$ días restantes) o intervenciones correctivas pendientes.
   - 🟡 **Urgencia Media (Amarillo / Ámbar):** Motores con mantenimiento preventivo programado a vencer dentro de los próximos 15 días.
   - 🟢 **Urgencia Baja (Verde):** Motores al día y operativos ($> 15$ días restantes).
   - Filtros instantáneos en la interfaz web por color de semáforo y área del molino.

3. **Auditoría Energética y Facturación Eléctrica (~S/. 70,000/mes):**
   - Módulo de registro de consumo en kWh e importe facturado en Soles (S/.).
   - Tarifa industrial promedio de referencia: S/. 0.422 / kWh.
   - Monitoreo gráfico dual en tiempo real: Consumo energético (kWh) vs. Facturación en Soles (S/.).

4. **Línea Base ISO 50006 y Modelo Predictivo (EnPI):**
   - 24 meses de datos históricos del pilado de arroz (arroz cáscara ingresado vs. arroz pilado obtenido).
   - Ajuste de regresión validado ($R^2 > 0.99$, $RMSE = 0.123\text{ kWh/ton}$, $MAPE = 0.18\%$).
   - Simulador interactivo en web para proyectar consumos, ahorros porcentuales y ahorros monetarios en soles (S/./mes).

---

## Estructura del proyecto

```
proyecto_tesis/
├── modelo_predictivo/          -> Específico 2 y 5 de la matriz de consistencia
│   ├── datos_simulados.csv         Datos de línea base (24 meses: arroz cáscara, arroz pilado, kWh, S/. 70k)
│   ├── analisis_correlacion.py     Correlación de Pearson + Generación de heatmap
│   ├── modelo_regresion.py         Regresión OLS + Validación (R², RMSE, MAPE) + Escenarios + Gráficos
│   ├── matriz_correlacion.png      [Figura Tesis] Mapa de calor de correlaciones
│   ├── enpi_real_vs_predicho.png   [Figura Tesis] Dispersión Real vs Predicho (Línea Base ISO 50006)
│   ├── linea_base_temporal.png     [Figura Tesis] Evolución temporal del EnPI en los 24 meses
│   ├── analisis_residuos.png       [Figura Tesis] Homocedasticidad y normalidad de residuos
│   └── resumen_modelo_tesis.txt    [Reporte Tesis] Ecuación matemática, métricas y tabla ANOVA
│
└── sistema_mantenimiento/      -> Específico 1 y 3 de la matriz de consistencia
    ├── app.py                      Punto de entrada con generador del parque de 130 motores
    ├── models.py                   Tablas: Usuario, Equipo (HP, semáforo), RegistroMantenimiento, RegistroConsumo
    ├── extensions.py               Inicialización de SQLAlchemy y Flask-Login
    ├── decoradores.py              Control de acceso por rol (@requiere_rol)
    ├── servicio_predictivo.py      Integración del modelo predictivo y simulador económico
    ├── routes/
    │   ├── auth.py                 Login / logout institucional
    │   ├── tecnico.py              Rutas del rol "técnico" (registro de mantenimiento en campo, consulta 130 motores)
    │   └── encargado.py            Rutas del "encargado" (validación, KPIs, semáforo, gráficas, simulador EnPI, CSV)
    ├── templates/                  Vistas HTML (Bootstrap 5, Bootstrap Icons, responsive)
    │   ├── base.html               Plantilla base corporativa Molino La Corona
    │   ├── dashboard_encargado.html Panel con KPIs, semáforo interactivo de 3 colores y tabla de estados
    │   ├── simulador_enpi.html     Auditoría Energética & Simulador interactivo de EnPI y ahorro en soles
    │   ├── graficos.html           Visualización interactiva de kWh y Facturación en Soles (Chart.js)
    │   ├── registrar_consumo.html  Ingreso de lecturas energéticas y recibo de luz (~S/. 70k)
    │   ├── equipos_lista.html      Gestión de fichas técnicas con filtro de 3 colores para los 130 motores
    │   ├── equipo_editar.html      Edición de potencia (HP y kW), horas de uso y frecuencias
    │   ├── validar_registro.html   Supervisión y visto bueno técnico
    │   ├── registrar_mantenimiento.html Formulario de campo para técnicos con semáforo por motor
    │   ├── historial_tecnico.html  Historial personal de consulta del técnico
    │   ├── equipos_lista_tecnico.html Fichas técnicas en modo consulta con semáforo
    │   └── login.html              Acceso institucional seguro
    └── static/
        └── style.css               Estilos corporativos Molino La Corona y semáforo de 3 colores
```

---

## Cómo responde el aplicativo a la Matriz de Consistencia

| Carpeta / Módulo | Específico | Qué demuestra ante el jurado |
|---|---|---|
| `sistema_mantenimiento/` (Consumo & Facturación) | **Específico 1** | Registro y control sistemático de consumos (kWh y S/.) por áreas del molino (Línea Base Energética según ISO 50001). |
| `modelo_predictivo/` | **Específico 2** | Correlación estadística de variables del proceso de pilado con el EnPI y ajuste de regresión validado ($R^2 > 0.99$, $RMSE = 0.123$, $MAPE = 0.18\%$). |
| `sistema_mantenimiento/` (Roles & Semáforo) | **Específico 3** | Separación estricta de privilegios y semáforo de 3 colores para priorizar el mantenimiento de los 130 motores según urgencia. |
| `modelo_predictivo/` + Simulador Web | **Específico 5** | Comparación cuantitativa del escenario base vs. escenarios con mejoras operativas en motores de 80 HP y ahorro mensual en Soles. |

---

## Instalación y Configuración

```bash
# 1. Activar entorno virtual
venv\Scripts\activate   # En Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno (.env)
# Copie .env.example a .env y configure según su entorno:
# - APP_MODE=demo         (Modo demostración con datos calibrados para la tesis)
# - APP_MODE=production   (Modo producción en limpio: 130 motores sin registros ficticios)
# - FLASK_DEBUG=False
# - SECRET_KEY=su-clave-secreta-criptografica
```

---

## Ejecución

### 1. Generar los Gráficos y Reportes Estadísticos de Molino La Corona
```bash
cd modelo_predictivo
python analisis_correlacion.py
python modelo_regresion.py
```
*Genera las 4 figuras PNG en alta resolución (300 DPI) y `resumen_modelo_tesis.txt` listo para la memoria de tesis.*

### 2. Iniciar la Plataforma Web
```bash
cd sistema_mantenimiento
python app.py
```
Abrir en el navegador: **`http://127.0.0.1:5000`**

### Migraciones de Base de Datos (Flask-Migrate / Alembic)
El proyecto utiliza Flask-Migrate para la gestión versionada de esquemas:
```bash
flask db migrate -m "descripción de cambio"
flask db upgrade
```

### Usuarios Iniciales y Seguridad:
| Usuario | Contraseña Inicial | Rol | Seguridad y Funcionalidades |
|---|---|---|---|
| `tecnico1` | `1234` | **Técnico** | *Cambio obligatorio de contraseña en el 1er ingreso*. Registra OTs en planta con formato FMT-MTO-01, historial y fichas técnicas. |
| `encargado1` | `1234` | **Encargado** | *Cambio obligatorio de contraseña en el 1er ingreso*. Admin Dashboard con barra lateral, semáforo de 3 colores, validación, consumos y Simulador EnPI. |
