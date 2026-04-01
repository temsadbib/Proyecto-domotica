import argparse
import json
import os
import random
import time
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_batch

ENTITIES = [
    ("sensor.sensor_temperatura_1_temperature", "temp", 21.0, 18.0, 26.0),
    ("sensor.sensor_temperatura_2_temperature", "temp", 20.5, 18.0, 26.0),
    ("sensor.sensor_temperatura_3_temperature", "temp", 20.0, 18.0, 26.0),
    ("sensor.sensor_temperatura_4_temperature", "temp", 19.8, 18.0, 26.0),
    ("sensor.sensor_temperatura_1_humidity", "humidity", 48.0, 35.0, 65.0),
    ("sensor.sensor_temperatura_2_humidity", "humidity", 47.0, 35.0, 65.0),
    ("sensor.sensor_temperatura_3_humidity", "humidity", 46.0, 35.0, 65.0),
    ("sensor.sensor_temperatura_4_humidity", "humidity", 46.0, 35.0, 65.0),
    ("sensor.sensor_temperatura_1_pressure", "inhg", 29.92, 29.5, 30.3),
    ("sensor.sensor_temperatura_2_pressure", "hpa", 1013.0, 1005.0, 1022.0),
    ("sensor.sensor_temperatura_3_pressure", "hpa", 1012.0, 1005.0, 1022.0),
    ("sensor.sensor_temperatura_4_pressure", "hpa", 1012.0, 1005.0, 1022.0),
    ("binary_sensor.sensor_puerta_1_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_1_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_2_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_3_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_4_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_5_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_6_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_7_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_8_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_9_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_10_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_11_contact", "binary", 0.0, 0.0, 1.0),
    ("binary_sensor.sensor_ventana_12_contact", "binary", 0.0, 0.0, 1.0),
    ("sensor.mislata_temperatura", "temp", 14.0, 5.0, 32.0),
    ("sensor.mislata_nubosidad", "pct", 40.0, 0.0, 100.0),
    ("sensor.mislata_humedad", "humidity", 55.0, 30.0, 90.0),
    ("sensor.mislata_viento", "wind", 8.0, 0.0, 40.0),
    ("sensor.sun_solar_elevation", "sun_el", 25.0, -25.0, 65.0),
    ("sensor.sun_solar_azimuth", "sun_az", 180.0, 0.0, 360.0),
]

CORR_GROUPS = {
    "temp_aula": [
        "sensor.sensor_temperatura_1_temperature",
        "sensor.sensor_temperatura_2_temperature",
        "sensor.sensor_temperatura_3_temperature",
        "sensor.sensor_temperatura_4_temperature",
    ],
    "hum_aula": [
        "sensor.sensor_temperatura_1_humidity",
        "sensor.sensor_temperatura_2_humidity",
        "sensor.sensor_temperatura_3_humidity",
        "sensor.sensor_temperatura_4_humidity",
    ],
    "pres_aula": [
        "sensor.sensor_temperatura_2_pressure",
        "sensor.sensor_temperatura_3_pressure",
        "sensor.sensor_temperatura_4_pressure",
    ],
}

SHARED_DRIFT = {
    "temp_aula": (-0.2, 0.2),
    "hum_aula": (-0.8, 0.8),
    "pres_aula": (-0.3, 0.3),
}

INDIVIDUAL_NOISE = {
    "temp": (-0.03, 0.03),
    "humidity": (-0.15, 0.15),
    "hpa": (-0.05, 0.05),
}

ENTITY_TO_GROUP = {}
for _grp, _members in CORR_GROUPS.items():
    for _eid in _members:
        ENTITY_TO_GROUP[_eid] = _grp


def parse_float_state(raw):
    if raw is None or raw in ("unavailable", "unknown", ""):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def load_last_states(conn):
    ids = [e[0] for e in ENTITIES]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (entity_id) entity_id, state
            FROM ltss
            WHERE entity_id = ANY(%s)
            ORDER BY entity_id, time DESC
            """,
            (ids,),
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def step_value(kind, current, lo, hi, rng, shared_drift=None):
    if kind == "binary":
        if rng.random() < 0.02:
            return 1.0 - current
        return current
    if kind == "sun_az":
        v = (current + rng.uniform(-8, 8)) % 360.0
        return max(lo, min(hi, v))
    if shared_drift is not None:
        lo_n, hi_n = INDIVIDUAL_NOISE.get(kind, (0.0, 0.0))
        v = current + shared_drift + rng.uniform(lo_n, hi_n)
        return max(lo, min(hi, v))
    noise = {
        "temp": rng.uniform(-0.35, 0.35),
        "humidity": rng.uniform(-1.2, 1.2),
        "inhg": rng.uniform(-0.02, 0.02),
        "hpa": rng.uniform(-0.4, 0.4),
        "pct": rng.uniform(-2, 2),
        "wind": rng.uniform(-1.5, 1.5),
        "sun_el": rng.uniform(-2, 2),
    }.get(kind, 0.0)
    v = current + noise
    return max(lo, min(hi, v))


def format_state(kind, v):
    if kind == "binary":
        return "on" if v >= 0.5 else "off"
    if kind in ("temp", "inhg", "hpa", "humidity", "pct", "wind", "sun_el", "sun_az"):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return str(v)


def build_rows(states, rng):
    ts = datetime.now(timezone.utc)
    group_drifts = {}
    for grp, (lo_d, hi_d) in SHARED_DRIFT.items():
        group_drifts[grp] = rng.uniform(lo_d, hi_d)
    rows = []
    for eid, kind, default, lo, hi in ENTITIES:
        raw = states.get(eid)
        parsed = parse_float_state(raw) if kind != "binary" else None
        if kind == "binary":
            cur = 1.0 if raw == "on" else 0.0
        else:
            cur = parsed if parsed is not None else default
        group = ENTITY_TO_GROUP.get(eid)
        drift = group_drifts.get(group) if group else None
        nxt = step_value(kind, cur, lo, hi, rng, shared_drift=drift)
        if kind == "binary":
            states[eid] = "on" if nxt >= 0.5 else "off"
        else:
            states[eid] = format_state(kind, nxt)
        st = states[eid]
        rows.append((ts, eid, st, json.dumps({})))
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.environ.get("PGHOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PGPORT", "5432")))
    p.add_argument("--dbname", default=os.environ.get("PGDATABASE", "postgres"))
    p.add_argument("--user", default=os.environ.get("PGUSER", "postgres"))
    p.add_argument("--password", default=os.environ.get("PGPASSWORD", "Qwe1234."))
    p.add_argument("--interval", type=float, default=5.0)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--once", action="store_true")
    args = p.parse_args()

    rng = random.Random(args.seed)
    conn = None
    for attempt in range(30):
        try:
            conn = psycopg2.connect(
                host=args.host,
                port=args.port,
                dbname=args.dbname,
                user=args.user,
                password=args.password,
            )
            conn.autocommit = True
            break
        except psycopg2.OperationalError:
            time.sleep(2)
    if conn is None:
        raise SystemExit("Could not connect to database after 30 attempts")

    states = {}
    for eid, kind, default, lo, hi in ENTITIES:
        if kind == "binary":
            states[eid] = "off"
        else:
            states[eid] = format_state(kind, default)

    try:
        last = load_last_states(conn)
        for eid, kind, default, lo, hi in ENTITIES:
            if eid not in last:
                continue
            raw = last[eid]
            if kind == "binary":
                states[eid] = raw if raw in ("on", "off") else "off"
            else:
                pv = parse_float_state(raw)
                if pv is not None:
                    states[eid] = format_state(kind, max(lo, min(hi, pv)))
    except Exception:
        pass

    sql = 'INSERT INTO ltss ("time", entity_id, state, attributes) VALUES (%s, %s, %s, %s::jsonb)'
    try:
        while True:
            batch = build_rows(states, rng)
            with conn.cursor() as cur:
                execute_batch(cur, sql, batch, page_size=50)
            if args.once:
                break
            time.sleep(args.interval)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
