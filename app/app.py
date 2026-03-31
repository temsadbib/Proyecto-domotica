import sys
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go

_ROOT = Path(__file__).resolve().parent
_APP = _ROOT / "app"
if _APP.is_dir():
    sys.path.insert(0, str(_APP))
from predictor import predict

MES_NOMBRES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)
DIA_NOMBRES = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)

st.set_page_config(
    page_title="Predicción de derroche energético",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .main .block-container { padding-top: 1.25rem; max-width: 1180px; }
    h1 {
        letter-spacing: -0.02em;
        font-weight: 700;
        color: #4A4B8B !important;
    }
    [data-testid="stForm"] {
        border: 2px solid #4A4B8B !important;
        border-radius: 8px;
    }
    div.stButton > button[kind="primaryFormSubmit"],
    div.stButton > button:first-child {
        background-color: #4A4B8B;
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    div.stButton > button[kind="primaryFormSubmit"]:hover,
    div.stButton > button:first-child:hover {
        background-color: #38396B;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Predicción de derroche energético")
st.caption(
    "Introduce la situación actual del aula. Se estima si habrá **derroche** en la **hora siguiente**"
)

modelo_pt = _ROOT / "models" / "model_derroche_v2.pt"
escala_jb = _ROOT / "models" / "scaler_derroche_v2.joblib"
st.caption(
    f"Modelo: `{modelo_pt.name}` — "
    f"{'encontrado' if modelo_pt.is_file() else 'no encontrado'} · "
    f"Scaler: `{escala_jb.name}` — {'encontrado' if escala_jb.is_file() else 'no encontrado'}"
)

col_entrada, col_resultado = st.columns([1.15, 0.85], gap="large")

with col_entrada:
    with st.form("formulario_derroche"):
        with st.container(border=True):
            st.subheader("Calendario y hora")
            c1, c2, c3 = st.columns(3)
            with c1:
                hora_del_dia = st.number_input("Hora del día", min_value=0, max_value=23, value=12, step=1)
            with c2:
                dia_de_la_semana = st.selectbox(
                    "Día de la semana",
                    options=list(range(1, 8)),
                    index=2,
                    format_func=lambda x: DIA_NOMBRES[x - 1],
                )
            with c3:
                mes_del_ano = st.selectbox(
                    "Mes",
                    options=list(range(1, 13)),
                    index=8,
                    format_func=lambda x: MES_NOMBRES[x - 1],
                )

        with st.container(border=True):
            st.subheader("Interior")
            r1, r2, r3 = st.columns(3)
            with r1:
                temp_aula = st.slider("Temperatura media (°C)", 15.0, 35.0, 22.0, 0.1)
            with r2:
                hum_aula = st.slider("Humedad media (%)", 30.0, 90.0, 50.0, 0.1)
            with r3:
                pres_aula = st.slider("Presión media (hPa)", 980.0, 1040.0, 1013.0, 0.1)

        with st.container(border=True):
            st.subheader("Exterior y sol")
            x1, x2, x3 = st.columns(3)
            with x1:
                temp_exterior = st.slider("Temp. exterior (°C)", -5.0, 42.0, 18.0, 0.1)
                nubosidad = st.slider("Nubosidad (0–10)", 0.0, 10.0, 3.0, 0.1)
            with x2:
                hum_exterior = st.slider("Humedad exterior (%)", 20.0, 100.0, 55.0, 0.1)
                vel_viento = st.slider("Viento (km/h)", 0.0, 60.0, 8.0, 0.1)
            with x3:
                elevacion_sol = st.slider("Elevación sol (°)", -30.0, 90.0, 35.0, 0.1)
                acimut_sol = st.slider("Acimut sol (°)", 0.0, 360.0, 180.0, 0.1)

        with st.container(border=True):
            st.subheader("Calefacción")
            calefaccion_encendida = st.radio(
                "Estado",
                options=[0.0, 1.0],
                horizontal=True,
                format_func=lambda v: "Apagada" if v == 0.0 else "Encendida",
            )

        with st.expander("Lecturas previas (opcional — mejoran la predicción)"):
            st.caption(
                "Si dispones de las lecturas de las horas anteriores, introdúcelas aquí. "
                "Si no, se usarán los valores actuales como aproximación."
            )
            p1, p2, p3 = st.columns(3)
            with p1:
                st.markdown("**Hace 1 h**")
                prev1_temp_aula = st.number_input("Temp. aula -1 h (°C)", value=22.0, step=0.1, key="p1ta")
                prev1_temp_ext = st.number_input("Temp. ext. -1 h (°C)", value=18.0, step=0.1, key="p1te")
                prev1_calef = st.selectbox(
                    "Calefacción -1 h", [0.0, 1.0], key="p1c",
                    format_func=lambda v: "Apagada" if v == 0.0 else "Encendida",
                )
            with p2:
                st.markdown("**Hace 2 h**")
                prev2_temp_aula = st.number_input("Temp. aula -2 h (°C)", value=22.0, step=0.1, key="p2ta")
                prev2_temp_ext = st.number_input("Temp. ext. -2 h (°C)", value=18.0, step=0.1, key="p2te")
                prev2_calef = st.selectbox(
                    "Calefacción -2 h", [0.0, 1.0], key="p2c",
                    format_func=lambda v: "Apagada" if v == 0.0 else "Encendida",
                )
            with p3:
                st.markdown("**Hace 3 h**")
                prev3_temp_aula = st.number_input("Temp. aula -3 h (°C)", value=22.0, step=0.1, key="p3ta")
                prev3_temp_ext = st.number_input("Temp. ext. -3 h (°C)", value=18.0, step=0.1, key="p3te")
                prev3_calef = st.selectbox(
                    "Calefacción -3 h", [0.0, 1.0], key="p3c",
                    format_func=lambda v: "Apagada" if v == 0.0 else "Encendida",
                )

        enviar = st.form_submit_button("Predecir derroche en la siguiente hora", type="primary", use_container_width=True)

features = {
    "hora_del_dia": hora_del_dia,
    "dia_de_la_semana": dia_de_la_semana,
    "mes_del_ano": mes_del_ano,
    "temp_aula": temp_aula,
    "hum_aula": hum_aula,
    "pres_aula": pres_aula,
    "temp_exterior": temp_exterior,
    "nubosidad": nubosidad,
    "hum_exterior": hum_exterior,
    "vel_viento": vel_viento,
    "elevacion_sol": elevacion_sol,
    "acimut_sol": acimut_sol,
    "calefaccion_encendida": calefaccion_encendida,
    "prev_1h": {
        "temp_aula": prev1_temp_aula,
        "temp_exterior": prev1_temp_ext,
        "calefaccion_encendida": prev1_calef,
    },
    "prev_2h": {
        "temp_aula": prev2_temp_aula,
        "temp_exterior": prev2_temp_ext,
        "calefaccion_encendida": prev2_calef,
    },
    "prev_3h": {
        "temp_aula": prev3_temp_aula,
        "temp_exterior": prev3_temp_ext,
        "calefaccion_encendida": prev3_calef,
    },
}

with col_resultado:
    st.subheader("Predicción del Modelo")

    st.markdown(
        f"""
        <div style="background-color: rgba(74, 75, 139, 0.12); border: 1px solid rgba(74, 75, 139, 0.35); color: #4A4B8B; font-weight: 600; padding: 0.85rem 1rem; border-radius: 8px; margin-bottom: 1rem;">
            Ventana objetivo: {hora_del_dia}:00 → {(hora_del_dia + 1) % 24}:00
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not enviar:
        st.markdown(
            """
            <div style="text-align: center; padding: 3rem 1rem; color: #6B7280; border: 2px dashed #E5E7EB; border-radius: 10px;">
                <h4>Esperando datos...</h4>
                <p>Configura los parámetros y pulsa el botón para generar la predicción.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        try:
            pred, prob = predict(features, model_path=modelo_pt, scaler_path=escala_jb)
            p_derroche = prob
            p_no = 1.0 - prob

            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=p_derroche * 100,
                number={"suffix": "%", "font": {"size": 48, "color": "#FF4B4B" if pred == 1 else "#00CC96"}},
                title={"text": "Probabilidad de Derroche", "font": {"size": 20}},
                domain={"x": [0, 1], "y": [0, 1]},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "darkgray"},
                    "bar": {"color": "#FF4B4B" if pred == 1 else "#00CC96"},
                    "bgcolor": "rgba(0,0,0,0)",
                    "borderwidth": 2,
                    "bordercolor": "gray",
                    "steps": [
                        {"range": [0, 50], "color": "rgba(0, 204, 150, 0.15)"},
                        {"range": [50, 100], "color": "rgba(255, 75, 75, 0.15)"},
                    ],
                    "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 50},
                },
            ))
            fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

            if pred == 1:
                st.error("**ALERTA DE DERROCHE:** Se prevé que el sistema consumirá energía de forma ineficiente. Se recomienda apagar la calefacción o ventilar.")
            else:
                st.success("**SISTEMA EFICIENTE:** Las condiciones son óptimas. No se prevé un derroche energético en la próxima hora.")

            c1, c2 = st.columns(2)
            c1.metric("P(Derroche)", f"{p_derroche:.2%}")
            c2.metric("P(Eficiente)", f"{p_no:.2%}")

        except FileNotFoundError:
            st.error(
                f"Faltan archivos del modelo o del escalador. Ejecuta la última celda de "
                f"`04b_model_nn_improved.ipynb` para generar `{modelo_pt.name}` y `{escala_jb.name}`."
            )
        except Exception as e:
            st.error(f"No se pudo completar la predicción: {e}")

st.divider()
st.caption(
    "Proyecto de eficiencia energética"
)
