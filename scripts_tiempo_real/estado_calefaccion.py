from __future__ import annotations

from pathlib import Path
from typing import Any, List, Sequence

import joblib
import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_MODEL = _ROOT / "models" / "calefaccion_linear.joblib"


def _load_bundle(path: Path | None = None):
    p = path or _DEFAULT_MODEL
    return joblib.load(p)


def algoritmo_termostato_raw(dia: int, hora: int, temp: float) -> float:
    if dia > 5:
        return 0.0
    if (7 <= hora < 16) or (18 <= hora <= 20):
        if temp < 21.9:
            return 1.0
        if temp > 22.0:
            return 0.0
        return float("nan")
    if 16 <= hora < 18:
        if temp < 21.5:
            return 1.0
        if temp > 21.6:
            return 0.0
        return float("nan")
    return 0.0


def _row_to_series(row: dict[str, Any], ts: pd.Timestamp) -> pd.Series:
    ta = float(row["temp_aula"] or 20.0)
    return pd.Series(
        {
            "temp_aula": ta,
            "hum_aula": float(row["hum_aula"] or 50.0),
            "pres_aula": float(row["pres_aula"] or 1013.0),
            "min_puerta_1": float(row["min_puerta_1"] or 0.0),
            "min_ventana_1": float(row["min_ventana_1"] or 0.0),
            "min_ventana_2": float(row["min_ventana_2"] or 0.0),
            "min_ventana_3": float(row["min_ventana_3"] or 0.0),
            "min_ventana_4": float(row["min_ventana_4"] or 0.0),
            "min_ventana_5": float(row["min_ventana_5"] or 0.0),
            "min_ventana_6": float(row["min_ventana_6"] or 0.0),
            "min_ventana_7": float(row["min_ventana_7"] or 0.0),
            "min_ventana_8": float(row["min_ventana_8"] or 0.0),
            "min_ventana_9": float(row["min_ventana_9"] or 0.0),
            "min_ventana_10": float(row["min_ventana_10"] or 0.0),
            "min_ventana_11": float(row["min_ventana_11"] or 0.0),
            "min_ventana_12": float(row["min_ventana_12"] or 0.0),
            "temp_exterior": float(row["temp_exterior"] or 15.0),
            "nubosidad": float(row["nubosidad"] or 0.0),
            "hum_exterior": float(row["hum_exterior"] or 50.0),
            "vel_viento": float(row["vel_viento"] or 0.0),
            "elevacion_sol": float(row["elevacion_sol"] or 0.0),
            "acimut_sol": float(row["acimut_sol"] or 180.0),
            "hora_del_dia": int(ts.hour),
            "dia_de_la_semana": int(ts.isoweekday()),
            "mes_del_ano": int(ts.month),
        }
    )


def compute_calefaccion_encendida_batch(
    rows: Sequence[dict[str, Any]],
    timestamps: Sequence[pd.Timestamp],
    bundle: dict | None = None,
) -> List[float]:
    if not rows:
        return []
    b = bundle if bundle is not None else _load_bundle()
    pipeline = b["pipeline"]
    feature_cols: List[str] = b["feature_cols"]
    X = pd.DataFrame(
        [_row_to_series(rows[i], pd.Timestamp(timestamps[i]))[feature_cols] for i in range(len(rows))],
        columns=feature_cols,
    )
    temps_inferidos = pipeline.predict(X)
    raw_reglas = []
    for i, row in enumerate(rows):
        ts = pd.Timestamp(timestamps[i])
        ta = float(row["temp_aula"] or 20.0)
        raw_reglas.append(algoritmo_termostato_raw(int(ts.isoweekday()), int(ts.hour), ta))
    s = pd.Series(raw_reglas, dtype=float)
    regla_ffill = s.ffill().fillna(0.0).astype(float).tolist()
    out: List[float] = []
    for i in range(len(rows)):
        inferida_sensor = 1.0 if float(temps_inferidos[i]) > 27.0 else 0.0
        reg = regla_ffill[i]
        val = 1.0 if inferida_sensor >= 0.5 else float(reg)
        out.append(val)
    return out
