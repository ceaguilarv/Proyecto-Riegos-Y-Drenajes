# Auditoría final del proyecto ET estación–satélite

## Estado general

La serie meteorológica fue corregida y validada temporalmente. El rango real de estación es 2025-07-30 a 2026-01-13, con 143 días válidos para análisis.

## Resultado Sentinel-2

Después de corregir fechas y reprocesar, la rama Sentinel-2 produjo 8 observaciones analysis-ready. El mejor modelo para ET diaria del mismo día fue:

- Target: ET diaria de estación.
- Predictor: SAVI_mean.
- n: 8.
- r: 0.9.
- R²: 0.81.
- RMSE: 0.173 mm/día.

Este resultado se interpreta como evidencia exploratoria de asociación entre un proxy espectral y la ET de estación, no como validación de ET satelital.

## Resultado Landsat/LST

La rama Landsat/LST produjo 4 coincidencias válidas estación–LST. Esto no es suficiente para regresiones robustas. La rama se conserva como diagnóstico térmico exploratorio y como justificación de una línea futura.

## Decisión para el informe

- Usar Sentinel-2 como resultado principal.
- Presentar Landsat/LST como diagnóstico complementario.
- No forzar regresiones térmicas.
- Mantener lenguaje prudente: asociación, proxy, exploratorio.
