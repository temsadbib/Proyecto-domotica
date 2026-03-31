# Informe Técnico: Proyecto de Eficiencia Energética del Aula

---

## 1. Introducción y contexto

El proyecto tiene como objetivo diseñar y construir una solución basada en datos para la **detección y predicción de derroche energético** en un aula del centro educativo. Se define *derroche* como la situación en la que la calefacción está encendida mientras las puertas o ventanas permanecen abiertas durante un tiempo significativo, provocando un consumo energético innecesario.

El aula está equipada con una infraestructura IoT compuesta por sensores Zigbee y un sistema domótico basado en **Home Assistant**, que recoge datos históricos de forma continua.

### 1.1 Objetivo principal

Construir un modelo de inteligencia artificial capaz de **predecir si habrá derroche energético en la hora siguiente**, dados los valores actuales de los sensores del aula. Se trata de un problema de **clasificación binaria** donde:

| Clase | Significado |
|-------|-------------|
| **0** | No habrá derroche en la siguiente hora |
| **1** | Habrá derroche en la siguiente hora |

### 1.2 Definición de derroche

Se considera derroche cuando, en una hora determinada, la calefacción está encendida y las puertas o ventanas han permanecido abiertas más de un umbral del 20 % de la hora, equivalente a 12 minutos ponderados. Se aplica una ponderación: la puerta cuenta el doble que una ventana inferior, y cada ventana inferior el doble que una superior.

### 1.3 Target del modelo

Se considera derroche cuando, en una hora determinada, la calefacción está encendida y las puertas o ventanas han permanecido abiertas más de un umbral de minutos. Se aplica una ponderación: la puerta cuenta el doble que una ventana inferior, de acuerdo con las indicaciones del proyecto.

---

## 2. Infraestructura disponible

### 2.1 Stack tecnológico

| Componente | Tecnología | Función |
|---|---|---|
| Servidor domótico | Home Assistant | Integración de sensores y fuentes externas |
| Broker MQTT | Mosquitto | Mensajería entre dispositivos |
| Pasarela Zigbee | Zigbee2MQTT + SLZB-06 | Comunicación con sensores Zigbee |
| Base de datos | TimescaleDB (PostgreSQL 15) | Almacenamiento de series temporales |
| Dashboard | Grafana | Visualización en tiempo real |
| Lenguaje | Python 3 | Análisis, modelado e interfaz |
| ML/IA | PyTorch, scikit-learn | Modelos de machine learning y redes neuronales |
| App de predicción | Streamlit + Plotly | Interfaz de usuario para predicciones |
| Contenedores | Docker Compose | Orquestación de servicios |

### 2.2 Sensores del aula

| Sensor | Modelo | Magnitudes |
|---|---|---|
| Temperatura/Humedad/Presión (×4) | Aqara WSDCGQ11LM | Temperatura (°C), humedad (%), presión (hPa) |
| Puerta (×1) | Aqara MCCGQ11LM | Estado abierto/cerrado |
| Ventanas (×12) | Aqara MCCGQ11LM | Estado abierto/cerrado |
| Consumo eléctrico | Shelly Pro EM-50 | Consumo (W) |

### 2.3 Integraciones externas en Home Assistant

| Integración | Datos |
|---|---|
| Met.no (Mislata) | Temperatura exterior, nubosidad, humedad, viento |
| Sun | Elevación solar, acimut solar |

### 2.4 Base de datos

La tabla principal es `public.ltss`, que almacena el histórico de Home Assistant:

```sql
CREATE TABLE public.ltss (
  "time"      timestamptz NOT NULL,
  entity_id   varchar     NOT NULL,
  state       varchar     NULL,
  attributes  jsonb       NULL
);
```

---

## 3. Arquitectura de datos: Medallion (Bronze → Silver → Gold)

Se ha implementado una arquitectura de datos por capas (medallion), materializada como vistas SQL en TimescaleDB y complementada con notebooks de Python.

### 3.1 Capa Bronze — Datos crudos filtrados

**Vista:** `bronze_sensores` (`sql/01_bronze_extract.sql`)

**Decisión:** Filtrar de la tabla `ltss` únicamente las entidades relevantes para el proyecto: los 4 sensores de temperatura/humedad/presión, la puerta, las 12 ventanas y los sensores externos (meteorología y sol).

**Justificación:** Reduce el volumen de datos a procesar y eliminar las entidades que no esten relacionadas.

```sql
CREATE OR REPLACE VIEW bronze_sensores AS
SELECT "time", entity_id, state, attributes
FROM ltss
WHERE entity_id IN (
    'sensor.sensor_temperatura_1_temperature',
    'sensor.sensor_temperatura_2_temperature',
    -- ... (4 sensores × 3 magnitudes + 1 puerta + 12 ventanas + 6 ext.)
);
```

### 3.2 Capa Silver — Limpieza y normalización

**Vista:** `silver_sensores` (`sql/02_silver_clean.sql`)

**Decisión:** Convertir los valores `state` (texto) a numéricos y unificar formatos:
- Sensores binarios (puertas/ventanas): `on → 1.0`, `off → 0.0`
- Sensor de presión 1: conversión de inHg a hPa (× 33.8639)
- Se descartan valores `unavailable`, `unknown` y vacíos

**Justificación:** Los datos originales de Home Assistant almacenan los valores como texto.Por lo que es imprescindible convertirlos a formato numérico para el análisis estadístico.

### 3.3 Capa Gold — Agregación por horas y features

**Vista:** `gold_features_horaria` (`sql/03_gold_features_hourly.sql` y `bd/init-scripts/03_vistas.sql`)

**Decisión:** Agregar los datos por hora y calcular:
- Media de temperatura, humedad y presión del aula
- Minutos con puerta/ventanas abiertas por hora
- Media de temperatura exterior, nubosidad, humedad exterior, velocidad del viento
- Media de elevación y acimut solar

**Justificación:** Trabajar a nivel horario reduce el ruido sin perder variacion relevantes en los datos.

Se dispone de dos variantes:
- `sql/03_gold_features_hourly.sql`: usa solo el **sensor 2** para temperatura/humedad/presión del aula (basado en el análisis de correlación que determina que los sensores son redundantes) ya que es el sensor con mayor cantidad datos.

### 3.4 Vista de correlaciones

**Vista:** `gold_correlaciones` (`sql/05_gold_correlaciones.sql`)

**Decisión:** Crear una vista para visualizar las correlaciones entres los diferentes sensores.

**Justificación:** Permite calcular correlación para determinar redundancia entre sensores.

---

## 4. Análisis exploratorio y correlaciones (Tareas 1-2)

El notebook `01_eda.ipynb` realiza el análisis exploratorio de datos, incluyendo:

### 4.1 Correlaciones entre sensores de temperatura

**Decisión:** Calculamos la correlación entre los 4 sensores de temperatura del aula.


<img width="643" height="530" alt="image" src="https://github.com/user-attachments/assets/f461d357-bb06-4e98-96a0-2c4f322ace98" />

**Conclusión:** Los sensores de temperatura presentan correlaciones muy altas entre sí (> 0.95), lo que indica alta **redundancia**. Es viable reducir a un único sensor representativo (Seleccionamos el **sensor 2** por tener la mayor cantidad de datos).

### 4.2 Correlaciones entre sensores de humedad

**Decisión:** Calculamos la correlación para los 4 sensores de humedad.

<img width="643" height="530" alt="image" src="https://github.com/user-attachments/assets/be5cce77-6866-4157-89f3-cd8e25c4a492" />


**Conclusión:** Patrón similar al de temperatura: alta correlación entre sensores, lo que confirma la redundancia. Se puede prescindir de 3 de los 4 sensores sin pérdida significativa de información.

---

## 5. Construcción del dataset Gold (Tareas 3-9)

El notebook `02_build_gold.ipynb` implementa todo el pipeline del flujo de datos:

### 5.1 Tarea 3: Recopilación y agregación horaria

**Decisión:** Leer la vista `gold_features_horaria` desde PostgreSQL y enriquecer:
- Variables de calendario: `hora_del_dia`, `dia_de_la_semana`, `mes_del_ano`
- Datos de calefacción: join con `data/bronze/historico_calefaccion.csv`
- Imputación de nulos

**Resultado:** `data/silver/dataset_tarea3_limpio.csv` — 3.925 registros horarios.

### 5.2 Tareas 4-5: Modelo ML lineal para temperatura de calefacción

**Decisión:** Entrenar un `LinearRegression` para **inferir la temperatura del sensor de calefacción** a partir de las condiciones del aula.

**Features de entrada:** `temp_aula`, `hum_aula`, `pres_aula`, `temp_exterior`, `nubosidad`, `elevacion_sol`, `acimut_sol`

**Métricas obtenidas:**

| Métrica | Train | Test |
|---------|-------|------|
| R² | 0.9334 | 0.5623 |
| MAE | 0.6789 | 0.7160 |
| RMSE | 0.9091 | 0.8997 |

**Coeficientes del modelo:**

| Feature | Coeficiente |
|---------|-------------|
| temp_aula | 0.7884 |
| hum_aula | -0.0492 |
| pres_aula | 0.0148 |
| temp_exterior | 0.0883 |
| nubosidad | 0.0014 |
| elevacion_sol | -0.0119 |
| acimut_sol | -0.0013 |
| intercept | -7.6510 |

**Justificación:** El coeficiente más alto corresponde a `temp_aula` (0.79), lo cual tiene sentido: la temperatura del sensor de calefacción está fuertemente correlacionada con la temperatura general del aula. El R² en test (0.56) indica un ajuste moderado, suficiente para la inferencia.

<img width="819" height="365" alt="image" src="https://github.com/user-attachments/assets/579320d9-5467-4135-a7dd-64a941e0a0e1" />

<img width="420" height="400" alt="image" src="https://github.com/user-attachments/assets/18728a3c-a978-47ba-846d-de5308455957" />

### 5.3 Tarea 6: Calefacción encendida

**Decisión:** Añadimos la columna `calefaccion_encendida` (0/1) basándose en la temperatura inferida por el modelo lineal y el algoritmo de encendido de la calefacción.

**Resultado:** `data/gold/dataset_tarea6.csv`

### 5.4 Tarea 7: Cálculo de derroche actual

**Decisión:** Calculamos los **minutos ponderados** que la puerta y ventanas estuvieron abiertas (la puerta cuenta como 2 ventanas inferiores y estas como dos superiores). Se define derroche_actual = 1 si calefaccion_encendida = 1 y los minutos totales ponderados de apertura son mayores que 12 minutos (20 % × 60 min).

**Resultado:** `data/gold/dataset_tarea7.csv`

<img width="1100" height="390" alt="image" src="https://github.com/user-attachments/assets/4d4fc5e7-6d22-45ff-8e28-2876cdb24671" />


### 5.5 Tarea 8: Derroche en la hora siguiente

**Decisión:** Creamos la columna `derroche_siguiente_hora` desplazando `derroche_actual` una hora hacia adelante.

**Justificación:** Este es el **target** del modelo de IA. Dado los datos de los sensores a una hora, queremos predecir si habrá derroche en la hora siguiente.

**Resultado:** `data/gold/dataset_tarea8.csv`

### 5.6 Tarea 9: Dataset final para IA

**Decisión:** Eliminamos las columnas intermedias (estado de puertas/ventanas, minutos abiertos, temperatura inferida de calefacción) dejando solo las features relevantes para el modelo.

**Justificación:** Las columnas eliminadas podrían generar ruido o sobreajuste.

**Columnas finales del dataset:**

| Columna | Descripción |
|---------|-------------|
| `hora_del_dia` | Hora (0-23) |
| `dia_de_la_semana` | Día (1-7) |
| `mes_del_ano` | Mes (1-12) |
| `temp_aula` | Temperatura media del aula (°C) |
| `hum_aula` | Humedad media del aula (%) |
| `pres_aula` | Presión media del aula (hPa) |
| `temp_exterior` | Temperatura exterior (°C) |
| `nubosidad` | Nubosidad (0-10) |
| `hum_exterior` | Humedad exterior (%) |
| `vel_viento` | Velocidad del viento (km/h) |
| `elevacion_sol` | Elevación solar (°) |
| `acimut_sol` | Acimut solar (°) |
| `calefaccion_encendida` | Estado de la calefacción (0/1) |
| `derroche_siguiente_hora` | **TARGET** — Derroche en la hora siguiente (0/1) |

**Resultado:** `data/gold/dataset_tarea9_final.csv` — 3.924 muestras (1.058 derroche, 2.866 no derroche → 26.96% positivos).

<img width="550" height="390" alt="image" src="https://github.com/user-attachments/assets/c31c7489-3f98-465b-922d-c3423bfae33e" />


---

## 6. Modelo de IA: Red Neuronal (Tarea 10)

Se han desarrollado dos versiones de la red neuronal, ambas en **PyTorch**.

### 6.1 Versión 1: RedDerroche (`04_model_nn.ipynb`)

**Arquitectura:**

```
Input (13 features)
  → Linear(13, 64) → ReLU → BatchNorm(64) → Dropout(0.3)
  → Linear(64, 32) → ReLU → BatchNorm(32) → Dropout(0.3)
  → Linear(32, 1) → Sigmoid
```

**Configuración de entrenamiento:**
- Función de pérdida: `BCEWithLogitsLoss` con `pos_weight` para compensar el desbalance de clases
- Optimizador: Adam (lr=1e-3)
- Scheduler: ReduceLROnPlateau
- Épocas: 1.000
- Batch size: 64
- Partición temporal (sin shuffle): 70% train / 15% validación / 15% test

**Métricas en validación:** Mejor Val F1 ≈ 0.89

### 6.2 Versión 2: RedDerrocheV2 (`04b_model_nn_improved.ipynb`) — Modelo final

**Mejoras respecto a V1:**

| Aspecto | V1 | V2 |
|---------|----|----|
| Features | 13 originales | 31 (originales + lag + cíclicas + interacción) |
| Codificación temporal | Directa | Cíclica (sin/cos para hora, día, mes) |
| Lags | No | 3h (temp_aula, temp_exterior, calefacción) |
| Deltas | No | Sí (variación 1h y 2h de temperatura) |
| Interacciones | No | `calef × diff_temp`, `calef × viento` |
| Activación | ReLU | GELU |
| Conexión residual | No | Sí (skip connection) |
| Función de pérdida | BCEWithLogitsLoss | Focal Loss (α=0.25, γ=2.0) |
| Optimizador | Adam | AdamW (weight_decay=1e-4) |
| Scheduler | ReduceLROnPlateau | CosineAnnealingWarmRestarts |
| Early stopping | No | Sí (patience=40) |
| Umbral | Fijo (0.5) | Optimizado por F1 en validación |
| Gradient clipping | No | Sí (max_norm=1.0) |
| Parámetros | ~3.500 | 46.081 |

**Arquitectura V2:**

```
Input (31 features)
  → Linear(31, 128) → BatchNorm(128) → GELU → Dropout(0.3)
  → Linear(128, 128) → BatchNorm(128) → GELU → Dropout(0.3) + Skip(residual)
  → Linear(128, 64) → BatchNorm(64) → GELU → Dropout(0.3)
  → Linear(64, 1) → Sigmoid
```

**Features de la V2 (31 columnas):**

Las 31 features se agrupan en:
- **Temporales cíclicas** (6): hora_sin, hora_cos, dia_sin, dia_cos, mes_sin, mes_cos
- **Ambiente interior** (3): temp_aula, hum_aula, pres_aula
- **Ambiente exterior** (4): temp_exterior, nubosidad, hum_exterior, vel_viento
- **Sol** (2): elevacion_sol, acimut_sol
- **Calefacción** (1): calefaccion_encendida
- **Lags 1-3h** (9): temp_aula_lag1/2/3, temp_exterior_lag1/2/3, calefaccion_lag1/2/3
- **Deltas** (3): delta_temp_aula_1h, delta_temp_aula_2h, delta_temp_exterior_1h
- **Interacciones** (3): diff_temp, calef_x_diff, calef_x_viento

**Entrenamiento:**
- Early stopping en época 67 (de 500 máximas)
- Mejor Val F1: **0.9706**
- Umbral óptimo: **0.50**

<img width="800" height="390" alt="image" src="https://github.com/user-attachments/assets/1549bbd8-dce9-40dc-a526-381ae02f7109" />


### 6.3 Métricas finales en test (V2)

| Métrica | Valor |
|---------|-------|
| **Accuracy** | 0.9083 |
| **Precision** | 0.7889 |
| **Recall** | 0.8987 |
| **F1-Score** | 0.8402 |
| **ROC-AUC** | 0.9660 |

**Matriz de confusión (test):**

|  | Predicho: No derroche | Predicho: Derroche |
|---|---|---|
| **Real: No derroche** | 393 | 38 |
| **Real: Derroche** | 16 | 142 |

**Informe de clasificación:**

| Clase | Precision | Recall | F1-Score | Support |
|---|---|---|---|---|
| No derroche | 0.96 | 0.91 | 0.94 | 431 |
| Derroche | 0.79 | 0.90 | 0.84 | 158 |
| **Accuracy** | | | **0.91** | **589** |
| **Macro avg** | 0.87 | 0.91 | 0.89 | 589 |
| **Weighted avg** | 0.91 | 0.91 | 0.91 | 589 |

**Justificación de métricas:**

Se ha priorizado el **F1-Score** y el **Recall** de la clase *derroche* porque:
- Es un problema con **clase minoritaria** (solo el 27% de las muestras son derroche)
- Es preferible tener algún falso positivo (alertar sin derroche real) que falsos negativos (no detectar un derroche real)
- El ROC-AUC de 0.9660 confirma que el modelo discrimina muy bien entre ambas clases

<img width="450" height="350" alt="image" src="https://github.com/user-attachments/assets/18ca5445-5118-4b50-8fd6-f067b5b57cc0" />


### 6.4 Regla de negocio adicional

Se implementó una regla determinista en el predictor: si `calefaccion_encendida == 0`, la predicción es automáticamente **no derroche** con probabilidad 0.0. Esto tiene sentido físico directo, ya que sin calefacción encendida no puede existir el derroche tal y como se ha definido.

---

## 7. Aplicación de predicción (Tarea 11)

### 7.1 Tecnología

La aplicación se ha desarrollado con **Streamlit** y **Plotly**.

**Archivo principal:** `app.py`
**Módulo de inferencia:** `app/predictor.py`
**Artefactos necesarios:** `models/modelo_derroche.pt`, `models/scaler_derroche.joblib`

### 7.2 Interfaz

La app presenta un formulario dividido en secciones:

1. **Calendario y hora**: Hora del día, día de la semana, mes del año
2. **Interior (aula)**: Temperatura, humedad y presión medias
3. **Exterior y sol**: Temperatura exterior, nubosidad, humedad exterior, viento, elevación y acimut solar
4. **Calefacción**: Estado encendida/apagada
5. **Lecturas previas (opcional)**: Datos de las 3 horas anteriores para mejorar la predicción (si no se proporcionan, se usan los valores actuales como aproximación)

### 7.3 Salida

Al pulsar "Predecir derroche en la siguiente hora", la app muestra:
- **Gauge**: Indicador de probabilidad de derroche (0-100%), con colores verde/rojo
- **Alerta o éxito**: Mensaje de alerta si se prevé derroche
- **Métricas**: P(Derroche) y P(Eficiente) como porcentajes
- **Ventana objetivo**: Indica el rango horario de la predicción (ej: "12:00 → 13:00")

---

## 8. Dashboard en Grafana

Los dashboards del proyecto son los siguientes:
| Archivo | Uso |
|---------|-----|
| `dashboard/Proyecto domótica - tiempo real.json` | Dashboard **en directo**|
| `dashboard/Proyecto domótica - estático.json` | Dashboard **histórico**|

**Paneles del dashboard estático:**
1. **Distribución del sensor**  
   - Tres gauges (*min*, *media*, *max*) de temperatura para el sensor elegido.
2. **Temperatura a lo largo del tiempo**  
   - Serie temporal de la temperatura del sensor seleccionado.
3. **Comparativa de todos los sensores**  
   - Serie con los cuatro sensores interiores y el sensor exterior.
4. **Humedad histórica**  
   - Serie con la humedad de los sensores interiores y humedad exterior.
5. **Meteorología histórica**  
   - T. Exterior y Nubosidad: temperatura exterior y porcentaje de nubosidad. 
   - Elevación solar y Viento: elevación solar y velocidad del viento.
6. **Análisis de derroche histórico**  
   - Derroche por hora del día y día de la semana: mapa de calor con el porcentaje de derroche.  
   - Derroche mensual: barras con las horas de derroche por mes.  
   - Minutos puertas y ventanas abiertas por mes: barras apiladas con la suma de minutos que han estado abiertas puertas y ventanas.

**Paneles del dashboard en tiempo real**

1. **Estado actual del aula**
   - Cinco gauges con las temperaturas de los cuantro sensores, humedad y temperatura exterior.
   - Estado de la calefacción.
   - Alerta de derroche.
   - Derroche por hora.
3. **Temperaturas hoy**
   - Serie con la temperatura de los cuatro sensores contra la exterior.
5. **Ambiente**
   - Humedad interior y exterior.
   - Viento y nubosidad.
7. **Puertas y ventanas**
   - Estado de puertas y ventanas.

---

## 9. Estructura del repositorio

```
proyecto_domotica_3/
├── requirements.txt                  # Dependencias Python
├── app/
│   ├── predictor.py                  # Módulo de inferencia PyTorch
│   └── app.py                     # App Streamlit de predicción
├── .streamlit/
│   └── config.toml                   # Tema de Streamlit
├── models/                           # Artefactos del modelo
│   ├── modelo_derroche.pt            # Modelo
│   └── scaler_derroche.joblib        # Scaler
├── docs/
│   └── informe-tecnico.md            # Informe técnico
├── data/
│   ├── bronze/
│   │   ├── dataset_sucio.csv          # Dataset con datos crudos
│   │   └── historico_calefaccion.csv  # Histórico de calefacción
│   ├── silver/
│   │   └── dataset_tarea3_limpio.csv  # Dataset limpio intermedio
│   └── gold/
│       ├── dataset_tarea6.csv         # Con calefacción encendida
│       ├── dataset_tarea7.csv         # Con derroche actual
│       ├── dataset_tarea8.csv         # Con derroche siguiente hora
│       └── dataset_tarea9_final.csv   # Dataset final para IA
├── sql/
│   ├── 01_bronze_extract.sql          # Vista bronze
│   ├── 02_silver_clean.sql            # Vista silver
│   ├── 03_gold_features_hourly.sql    # Vista gold (sensor 2)
│   ├── 04_grafana_live_silver.sql     # Vista para Grafana en tiempo real
│   └── 05_gold_correlaciones.sql      # Vista para correlaciones
├── notebooks/
│   ├── 01_eda.ipynb                   # Análisis exploratorio
│   ├── 02_build_gold.ipynb            # Construcción dataset gold
│   ├── 03_model_ml.ipynb              # Modelo ML lineal
│   ├── 04_model_nn.ipynb              # Red neuronal
│   └── 05_evaluation.ipynb            # Evaluación y métricas
├── bd/
│   ├── docker-compose.yml             # TimescaleDB + Grafana
│   └── init-scripts/
│       ├── 01_creacion.sql            # Creación tabla ltss
│       └── 02_datos.sql               # Volcado de datos
└── grafana/
    ├── dashboards/
    └── eficiencia_energetica.json     # Dashboard 
        └── provisioning/
            ├── dashboards/provider.yml
            └── datasources/timescaledb.yml
```

---

## 10. Resultados y conclusiones

### 10.1 Resumen de resultados

| Componente | Resultado |
|---|---|
| **Correlación sensores** | Alta redundancia entre los 4 sensores (> 0.95). Se puede reducir a 1 sensor. |
| **Modelo ML lineal** | R² = 0.56 (test) para inferir temperatura de calefacción. |
| **Red neuronal** | F1 = 0.84, ROC-AUC = 0.97 en test. Recall derroche = 0.90. |
| **App de predicción** | Acepta datos manuales y de horas previas. |
| **Dashboard Grafana** | Tiempo real con gauges y series temporales de los sensores. |

### 10.2 Conclusiones

1. **Sensores**: Los cuatro sensores del aula resultaron redundantes, por lo que nos quedamos con el sensor 2 por tener la mayor cantidad de datos.

2. **Calefacción**: El estado de la calefacción se infirió mediante un modelo lineal a partir de los datos del aula.

3. **Derroche**: El derroche se define como calefacción encendida cuando puertas y ventanas están abiertas más de un umbral de X minutos ponderados.

4. **Target**: El target del clasificador lo hemos construido desplazando esa señal una hora hacia adelante.

5. **Red Neuronal**: Hemos construido una red neuronal capaz de predecir si va a haber derroche en la siguiente hora si la calefacción está encendida.

6. **App**: Hemos creado una aplicación que permite introducir las lecturas actuales y, opcionalmente, las de las tres horas previas, mostrando la probabilidad de derroche.

### 10.3 Propuestas de mejora

1. **Alertas**: Implementar un sistema de alertas automáticas (email, notificación push) cuando el modelo prediga derroche.

2. **Reentrenamiento**: Actualizar el modelo con datos más recientes para mantener su precisión a lo largo del tiempo y adaptarse a cambios estacionales.

3. **Más variables**: Incorporar datos de consumo eléctrico.

4. **Modelo de series temporales**: Explorar arquitecturas como LSTM o Transformer para capturar mejor las dependencias temporales a largo plazo.
