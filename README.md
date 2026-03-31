# Eficiencia energética — predicción de derroche

Proyecto para estimar si habrá **derroche energético en la hora siguiente** en un aula (Home Assistant, sensores Zigbee, TimescaleDB). El derroche se define cuando la calefacción está encendida y puertas/ventanas permanecen abiertas más de un umbral de un 20% del tiempo en la hora.

**Salida del modelo:** clasificación binaria (0 = no derroche, 1 = derroche en la hora siguiente).

## Stack

- Python (pandas, scikit-learn, PyTorch), Jupyter
- Streamlit + Plotly (app de predicción)
- TimescaleDB / PostgreSQL, Grafana (Docker)

## Requisitos

- Python 3.10+
- Docker y Docker Compose

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
