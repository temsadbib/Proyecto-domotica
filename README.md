# Eficiencia energética — predicción de derroche

Proyecto para estimar si habrá **derroche energético en la hora siguiente** en el aula (Home Assistant, sensores Zigbee, TimescaleDB). El derroche se define cuando la calefacción está encendida y puertas/ventanas permanecen abiertas más de un umbral de un 20% del tiempo en la hora.

**Salida del modelo:** clasificación binaria (0 = no derroche, 1 = derroche en la hora siguiente).

### Estructura de directorios

* **`app/`** — App Streamlit de predicción
  * `app.py`
  * `predictor.py`
* **`dashboard/`**
  * `domotica - en directo.json` — Dashboard en tiempo real
  * `Proyecto domótica - estatico.json` — Dashboard estático
* **`docs/`** — Documentación del proyecto
  * `informe-tecnico.md`
* **`notebooks/`** — Notebooks (EDA, capa gold, modelo)
  * `01_eda.ipynb`
  * `02_build_gold.ipynb`
  * `03_model_nn.ipynb`
* **`slides/`** — Presentación del proyecto
  * `presentacion.pdf`
* **`scripts_tiempo_real/`** — Scripts de ingesta, simulación, predicción y entrenamiento en directo
  * `datos_simulados.py`
  * `estado_calefaccion.py`
  * `predict_derroche.py`
  * `relleno_datos.py`
  * `train_calefaccion.py`
* **`sql/`** — Scripts SQL (capas bronze, silver, gold, vistas y almacén de predicciones)
  * `01_bronze_extract.sql`
  * `02_silver_clean.sql`
  * `03_gold_features_hourly.sql`
  * `04_gold_correlaciones.sql`
  * `05_grafana_live_silver.sql`
  * `06_predicciones_live.sql`
* `docker-compose.yml`
* `docker-compose.live.yml` — Entorno en directo
