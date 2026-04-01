import argparse
import os
import sys
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd
import psycopg2

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_TR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_TR))
sys.path.insert(0, str(_ROOT / "app"))
from estado_calefaccion import compute_calefaccion_encendida_batch
from predictor import predict

MODEL_PATH = _ROOT / "models" / "model_derroche_v2.pt"
SCALER_PATH = _ROOT / "models" / "scaler_derroche_v2.joblib"

_GOLD_BODY = """
    SELECT
        fecha_hora_utc,
        temp_aula, hum_aula, pres_aula,
        min_puerta_1,
        min_ventana_1, min_ventana_2, min_ventana_3, min_ventana_4,
        min_ventana_5, min_ventana_6, min_ventana_7, min_ventana_8,
        min_ventana_9, min_ventana_10, min_ventana_11, min_ventana_12,
        temp_exterior, nubosidad, hum_exterior, vel_viento,
        elevacion_sol, acimut_sol
    FROM gold_features_horaria
"""

_GOLD_SQL_LIVE = _GOLD_BODY + """
    WHERE fecha_hora_utc >= now() - interval '4 hours'
    ORDER BY fecha_hora_utc ASC
"""

_GOLD_SQL_WINDOW = _GOLD_BODY + """
    WHERE fecha_hora_utc >= %s AND fecha_hora_utc <= %s
    ORDER BY fecha_hora_utc ASC
"""


def _rows_to_features(row_dicts):
    if not row_dicts:
        return None, None, None

    timestamps = [pd.Timestamp(row_dicts[i]["fecha_hora_utc"]) for i in range(len(row_dicts))]
    calef_vals = compute_calefaccion_encendida_batch(row_dicts, timestamps)

    current = row_dicts[-1]
    hora_ts = current["fecha_hora_utc"]
    hora_del_dia = int(timestamps[-1].hour)
    dia_de_la_semana = int(timestamps[-1].isoweekday())
    mes_del_ano = int(timestamps[-1].month)

    ta = float(current["temp_aula"] or 20.0)
    te = float(current["temp_exterior"] or 15.0)
    cal = float(calef_vals[-1])

    features = {
        "hora_del_dia": hora_del_dia,
        "dia_de_la_semana": dia_de_la_semana,
        "mes_del_ano": mes_del_ano,
        "temp_aula": ta,
        "hum_aula": float(current["hum_aula"] or 50.0),
        "pres_aula": float(current["pres_aula"] or 1013.0),
        "temp_exterior": te,
        "nubosidad": float(current["nubosidad"] or 0.0),
        "hum_exterior": float(current["hum_exterior"] or 50.0),
        "vel_viento": float(current["vel_viento"] or 0.0),
        "elevacion_sol": float(current["elevacion_sol"] or 0.0),
        "acimut_sol": float(current["acimut_sol"] or 180.0),
        "calefaccion_encendida": cal,
    }

    def row_to_prev(idx):
        d = row_dicts[idx]
        return {
            "temp_aula": float(d["temp_aula"] or ta),
            "temp_exterior": float(d["temp_exterior"] or te),
            "calefaccion_encendida": float(calef_vals[idx]),
        }

    n = len(row_dicts)
    if n >= 2:
        features["prev_1h"] = row_to_prev(n - 2)
    if n >= 3:
        features["prev_2h"] = row_to_prev(n - 3)
    if n >= 4:
        features["prev_3h"] = row_to_prev(n - 4)

    return hora_ts, features, cal


def get_hourly_features(conn):
    with conn.cursor() as cur:
        cur.execute(_GOLD_SQL_LIVE)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    if not rows:
        return None, None, None

    row_dicts = [dict(zip(cols, r)) for r in rows]
    return _rows_to_features(row_dicts)


def _fetch_window(conn, start_ts, end_ts):
    with conn.cursor() as cur:
        cur.execute(_GOLD_SQL_WINDOW, (start_ts, end_ts))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    if not rows:
        return None
    return [dict(zip(cols, r)) for r in rows]


def _upsert_prediction(conn, hora, prob, pred, calef_enc):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO predicciones_derroche (hora, probabilidad, prediccion, metodo, calefaccion_encendida)
            VALUES (%s, %s, %s, 'neural_network_v2', %s)
            ON CONFLICT (hora) DO UPDATE
            SET probabilidad = EXCLUDED.probabilidad,
                prediccion = EXCLUDED.prediccion,
                metodo = EXCLUDED.metodo,
                calefaccion_encendida = EXCLUDED.calefaccion_encendida
        """,
            (hora, prob, pred, calef_enc),
        )


def backfill_today(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT fecha_hora_utc FROM gold_features_horaria
            WHERE fecha_hora_utc >= date_trunc('day', now())
              AND fecha_hora_utc <= date_trunc('hour', now())
            ORDER BY fecha_hora_utc ASC
            """
        )
        hour_list = [r[0] for r in cur.fetchall()]

    written = 0
    for end_ts in hour_list:
        start_ts = end_ts - timedelta(hours=4)
        row_dicts = _fetch_window(conn, start_ts, end_ts)
        if not row_dicts:
            continue
        last_ts = row_dicts[-1]["fecha_hora_utc"]
        if pd.Timestamp(last_ts).floor("h") != pd.Timestamp(end_ts).floor("h"):
            continue
        hora_ts, features, calef_enc = _rows_to_features(row_dicts)
        if hora_ts is None or features is None:
            continue
        pred, prob = predict(features, model_path=MODEL_PATH, scaler_path=SCALER_PATH)
        _upsert_prediction(conn, hora_ts, prob, pred, calef_enc)
        written += 1

    print(f"Backfill del día: {written} horas en predicciones_derroche")


def run_prediction(conn):
    hora, features, calef_enc = get_hourly_features(conn)
    if hora is None or features is None:
        print("No hay datos suficientes en gold_features_horaria")
        return

    pred, prob = predict(features, model_path=MODEL_PATH, scaler_path=SCALER_PATH)
    _upsert_prediction(conn, hora, prob, pred, calef_enc)
    print(f"{hora}: calefaccion={calef_enc:.0f} prob={prob:.3f} pred={pred}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.environ.get("PGHOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PGPORT", "5432")))
    p.add_argument("--dbname", default=os.environ.get("PGDATABASE", "postgres"))
    p.add_argument("--user", default=os.environ.get("PGUSER", "postgres"))
    p.add_argument("--password", default=os.environ.get("PGPASSWORD", "Qwe1234."))
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--once", action="store_true")
    p.add_argument(
        "--no-backfill",
        action="store_true",
        help="No rellenar predicciones de las horas ya pasadas del día al arrancar",
    )
    args = p.parse_args()

    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
    )
    conn.autocommit = True

    print(f"Predictor iniciado (intervalo={args.interval}s)")
    try:
        if not args.no_backfill:
            try:
                backfill_today(conn)
            except Exception as e:
                print(f"Backfill: {e}")
        while True:
            try:
                run_prediction(conn)
            except Exception as e:
                print(f"Error: {e}")
            if args.once:
                break
            time.sleep(args.interval)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
