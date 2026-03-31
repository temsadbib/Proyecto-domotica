CREATE OR REPLACE VIEW gold_features_horaria AS
SELECT
    date_trunc('hour', "time") AS fecha_hora_utc,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_2_temperature') AS temp_aula,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_2_humidity') AS hum_aula,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sensor_temperatura_2_pressure') AS pres_aula,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_puerta_1_contact') * 60,
        1
    ) AS min_puerta_1,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_1_contact') * 60,
        1
    ) AS min_ventana_1,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_2_contact') * 60,
        1
    ) AS min_ventana_2,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_3_contact') * 60,
        1
    ) AS min_ventana_3,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_4_contact') * 60,
        1
    ) AS min_ventana_4,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_5_contact') * 60,
        1
    ) AS min_ventana_5,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_6_contact') * 60,
        1
    ) AS min_ventana_6,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_7_contact') * 60,
        1
    ) AS min_ventana_7,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_8_contact') * 60,
        1
    ) AS min_ventana_8,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_9_contact') * 60,
        1
    ) AS min_ventana_9,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_10_contact') * 60,
        1
    ) AS min_ventana_10,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_11_contact') * 60,
        1
    ) AS min_ventana_11,
    ROUND(
        AVG(state_numeric) FILTER (WHERE entity_id = 'binary_sensor.sensor_ventana_12_contact') * 60,
        1
    ) AS min_ventana_12,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.mislata_temperatura') AS temp_exterior,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.mislata_nubosidad') AS nubosidad,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.mislata_humedad') AS hum_exterior,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.mislata_viento') AS vel_viento,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sun_solar_elevation') AS elevacion_sol,
    AVG(state_numeric) FILTER (WHERE entity_id = 'sensor.sun_solar_azimuth') AS acimut_sol
FROM silver_sensores
WHERE entity_id IN (
    'sensor.sensor_temperatura_2_temperature',
    'sensor.sensor_temperatura_2_humidity',
    'sensor.sensor_temperatura_2_pressure',
    'binary_sensor.sensor_puerta_1_contact',
    'binary_sensor.sensor_ventana_1_contact',
    'binary_sensor.sensor_ventana_2_contact',
    'binary_sensor.sensor_ventana_3_contact',
    'binary_sensor.sensor_ventana_4_contact',
    'binary_sensor.sensor_ventana_5_contact',
    'binary_sensor.sensor_ventana_6_contact',
    'binary_sensor.sensor_ventana_7_contact',
    'binary_sensor.sensor_ventana_8_contact',
    'binary_sensor.sensor_ventana_9_contact',
    'binary_sensor.sensor_ventana_10_contact',
    'binary_sensor.sensor_ventana_11_contact',
    'binary_sensor.sensor_ventana_12_contact',
    'sensor.mislata_temperatura',
    'sensor.mislata_nubosidad',
    'sensor.mislata_humedad',
    'sensor.mislata_viento',
    'sensor.sun_solar_elevation',
    'sensor.sun_solar_azimuth'
)
GROUP BY date_trunc('hour', "time")
ORDER BY fecha_hora_utc ASC;
