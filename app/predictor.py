import numpy as np
import torch
import torch.nn as nn
import joblib
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


class RedDerroche(nn.Module):
    def __init__(self, input_dim, hidden_dims=(64, 32), dropout=0.3):
        super().__init__()
        layers = []
        prev = input_dim
        for h in hidden_dims:
            layers.extend([
                nn.Linear(prev, h),
                nn.ReLU(),
                nn.BatchNorm1d(h),
                nn.Dropout(dropout)
            ])
            prev = h
        self.encoder = nn.Sequential(*layers)
        self.classifier = nn.Linear(prev, 1)

    def forward(self, x):
        x = self.encoder(x)
        return self.classifier(x)


class RedDerrocheV2(nn.Module):
    def __init__(self, input_dim, hidden_dim=128, dropout=0.3):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.bn1 = nn.BatchNorm1d(hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.bn2 = nn.BatchNorm1d(hidden_dim)
        self.skip = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.bn3 = nn.BatchNorm1d(hidden_dim // 2)
        self.classifier = nn.Linear(hidden_dim // 2, 1)
        self.drop = nn.Dropout(dropout)
        self.act = nn.GELU()

    def forward(self, x):
        x = self.drop(self.act(self.bn1(self.fc1(x))))
        residual = x
        x = self.drop(self.act(self.bn2(self.fc2(x))))
        x = x + self.skip(residual)
        x = self.drop(self.act(self.bn3(self.fc3(x))))
        return self.classifier(x)


def _build_v2_features(features_dict, feature_cols):
    raw = features_dict
    hora = raw["hora_del_dia"]
    dia = raw["dia_de_la_semana"]
    mes = raw["mes_del_ano"]

    prev_1h = raw.get("prev_1h", {})
    prev_2h = raw.get("prev_2h", {})
    prev_3h = raw.get("prev_3h", {})

    ta = raw["temp_aula"]
    te = raw["temp_exterior"]
    cal = raw["calefaccion_encendida"]

    computed = {
        "hora_sin": np.sin(2 * np.pi * hora / 24),
        "hora_cos": np.cos(2 * np.pi * hora / 24),
        "dia_sin": np.sin(2 * np.pi * dia / 7),
        "dia_cos": np.cos(2 * np.pi * dia / 7),
        "mes_sin": np.sin(2 * np.pi * mes / 12),
        "mes_cos": np.cos(2 * np.pi * mes / 12),
        "temp_aula": ta,
        "hum_aula": raw["hum_aula"],
        "pres_aula": raw["pres_aula"],
        "temp_exterior": te,
        "nubosidad": raw["nubosidad"],
        "hum_exterior": raw["hum_exterior"],
        "vel_viento": raw["vel_viento"],
        "elevacion_sol": raw["elevacion_sol"],
        "acimut_sol": raw["acimut_sol"],
        "calefaccion_encendida": cal,
        "temp_aula_lag1": prev_1h.get("temp_aula", ta),
        "temp_aula_lag2": prev_2h.get("temp_aula", ta),
        "temp_aula_lag3": prev_3h.get("temp_aula", ta),
        "temp_exterior_lag1": prev_1h.get("temp_exterior", te),
        "temp_exterior_lag2": prev_2h.get("temp_exterior", te),
        "temp_exterior_lag3": prev_3h.get("temp_exterior", te),
        "calefaccion_lag1": prev_1h.get("calefaccion_encendida", cal),
        "calefaccion_lag2": prev_2h.get("calefaccion_encendida", cal),
        "calefaccion_lag3": prev_3h.get("calefaccion_encendida", cal),
        "delta_temp_aula_1h": ta - prev_1h.get("temp_aula", ta),
        "delta_temp_aula_2h": ta - prev_2h.get("temp_aula", ta),
        "delta_temp_exterior_1h": te - prev_1h.get("temp_exterior", te),
        "diff_temp": ta - te,
        "calef_x_diff": cal * (ta - te),
        "calef_x_viento": cal * raw["vel_viento"],
    }

    return np.array([[computed[c] for c in feature_cols]], dtype=np.float32)


def predict(features_dict, model_path=None, scaler_path=None):
    if features_dict.get("calefaccion_encendida", 1.0) == 0.0:
        return 0, 0.0
    if model_path is None:
        model_path = MODELS_DIR / "model_derroche.pt"
    if scaler_path is None:
        scaler_path = MODELS_DIR / "scaler_derroche.joblib"

    try:
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    except TypeError:
        checkpoint = torch.load(model_path, map_location="cpu")
    scaler = joblib.load(scaler_path)
    feature_cols = checkpoint["feature_cols"]
    input_dim = checkpoint["input_dim"]

    is_v2 = "hidden_dim" in checkpoint

    if is_v2:
        x = _build_v2_features(features_dict, feature_cols)
        hidden_dim = checkpoint["hidden_dim"]
        model = RedDerrocheV2(input_dim=input_dim, hidden_dim=hidden_dim)
        threshold = checkpoint.get("best_threshold", 0.5)
    else:
        x = np.array([[features_dict[c] for c in feature_cols]], dtype=np.float32)
        hidden_dims = checkpoint["hidden_dims"]
        model = RedDerroche(input_dim=input_dim, hidden_dims=hidden_dims)
        threshold = 0.5

    x_scaled = scaler.transform(x)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    with torch.no_grad():
        tensor_x = torch.tensor(x_scaled, dtype=torch.float32)
        logit = model(tensor_x)
        prob = torch.sigmoid(logit).item()

    pred = 1 if prob >= threshold else 0
    return pred, prob
