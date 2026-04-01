from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = _ROOT / "data" / "silver" / "dataset_tarea3_limpio.csv"
OUT_PATH = _ROOT / "models" / "calefaccion_linear.joblib"

_EXTRA_COLS = [
    "hora_sin",
    "hora_cos",
    "dow_sin",
    "dow_cos",
    "mes_sin",
    "mes_cos",
    "temp_aula_minus_exterior",
    "temp_calefaccion_lag1",
    "temp_aula_roll3",
    "temp_aula_roll24",
    "temp_calefaccion_inferida",
]


def main():
    df = pd.read_csv(CSV_PATH, index_col=0, parse_dates=True)
    df = df.sort_index()
    for c in _EXTRA_COLS:
        if c in df.columns:
            df = df.drop(columns=[c])
    df = df.dropna()
    X = df.drop(columns=["temp_calefaccion"])
    y = df["temp_calefaccion"]
    feature_cols = list(X.columns)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    modelo = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("reg", LinearRegression()),
        ]
    )
    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = r2_score(y_test, y_pred)
    print(f"MAE: {mae:.4f} RMSE: {rmse:.4f} R2: {r2:.4f}")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": modelo, "feature_cols": feature_cols}, OUT_PATH)
    print(f"Guardado: {OUT_PATH}")


if __name__ == "__main__":
    main()
