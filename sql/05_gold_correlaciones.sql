CREATE OR REPLACE VIEW gold_correlaciones AS
SELECT
    date_trunc('hour', "time") AS fecha_hora_utc,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_1_temperature') AS temp_aula_1,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_2_temperature') AS temp_aula_2,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_3_temperature') AS temp_aula_3,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_4_temperature') AS temp_aula_4,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_1_humidity') AS hum_aula_1,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_2_humidity') AS hum_aula_2,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_3_humidity') AS hum_aula_3,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_4_humidity') AS hum_aula_4,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_1_pressure') AS pres_aula_1,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_2_pressure') AS pres_aula_2,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_3_pressure') AS pres_aula_3,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_4_pressure') AS pres_aula_4,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.mislata_temperatura') AS temp_exterior
FROM silver_sensores
WHERE entity_id IN (
    'sensor.sensor_temperatura_1_temperature',
    'sensor.sensor_temperatura_2_temperature',
    'sensor.sensor_temperatura_3_temperature',
    'sensor.sensor_temperatura_4_temperature',
    'sensor.sensor_temperatura_1_humidity',
    'sensor.sensor_temperatura_2_humidity',
    'sensor.sensor_temperatura_3_humidity',
    'sensor.sensor_temperatura_4_humidity',
    'sensor.sensor_temperatura_1_pressure',
    'sensor.sensor_temperatura_2_pressure',
    'sensor.sensor_temperatura_3_pressure',
    'sensor.sensor_temperatura_4_pressure',
    'sensor.mislata_temperatura'
)
GROUP BY date_trunc('hour', "time")
ORDER BY fecha_hora_utc ASC;
