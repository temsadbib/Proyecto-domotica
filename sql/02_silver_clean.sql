CREATE OR REPLACE VIEW silver_sensores AS
SELECT
    "time",
    entity_id,
    CASE
        WHEN entity_id LIKE 'binary_sensor.%' THEN
            CASE WHEN state = 'on' THEN 1.0 WHEN state = 'off' THEN 0.0 END
        WHEN state ~ '^-?[0-9]+\.?[0-9]*$'
        THEN CAST(state AS DOUBLE PRECISION)
    END AS state_numeric
FROM bronze_sensores
WHERE state IS NOT NULL
  AND state NOT IN ('unavailable', 'unknown', '');
