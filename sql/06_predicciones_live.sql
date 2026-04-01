CREATE TABLE IF NOT EXISTS predicciones_derroche (
    hora        timestamptz PRIMARY KEY,
    probabilidad double precision NOT NULL,
    prediccion  integer NOT NULL,
    metodo      varchar NOT NULL DEFAULT 'heuristic'
);