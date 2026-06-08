# Borrador de resultados

## Resumen principal

Se analizaron 8 observaciones coincidentes entre la serie diaria de estación y Sentinel-2, distribuidas entre 2025-08-20 y 2025-12-28. El mejor desempeño para la ET del mismo día se observó con SAVI, con una relación alta y positiva frente a la ET de estación (r = 0.900, rho = 0.833, R² = 0.810, RMSE = 0.173 mm d⁻¹, MAE = 0.146 mm d⁻¹, n = 8). La ecuación del ajuste fue: ET = 0.773 + 5.137 × SAVI.

## Párrafo de resultados

En la comparación entre ET diaria de estación y proxies espectrales Sentinel-2, SAVI presentó el mejor ajuste para el mismo día. La correlación de Pearson alcanzó r = 0.900 y el coeficiente de determinación fue R² = 0.810, lo que indica que aproximadamente el 81.0% de la variabilidad observada en la ET diaria quedó capturada por una relación lineal simple con este índice. El error del ajuste fue moderado (RMSE = 0.173 mm d⁻¹; MAE = 0.146 mm d⁻¹), y la pendiente positiva (5.137) sugiere que valores más altos de SAVI tendieron a asociarse con mayores valores de ET de estación en la muestra analizada.

## Comparación entre predictores en ET del mismo día

El orden de desempeño para ET del mismo día fue: 1. SAVI (r = 0.900, R² = 0.810, RMSE = 0.173); 2. NDVI (r = 0.870, R² = 0.757, RMSE = 0.196); 3. NDRE (r = 0.843, R² = 0.710, RMSE = 0.214); 4. EVI (r = 0.811, R² = 0.657, RMSE = 0.233).

## Perfil temporal del mejor predictor

Tomando SAVI como predictor focal, el patrón por escalas temporales fue el siguiente:
- ET diaria (mismo día): r = 0.900, rho = 0.833
- ET media móvil 3 días (incluye día satelital): r = 0.596, rho = 0.762
- ET media móvil 5 días (incluye día satelital): r = 0.588, rho = 0.524
- ET media móvil 7 días (incluye día satelital): r = 0.395, rho = 0.262
- ET acumulada 3 días (incluye día satelital): r = 0.596, rho = 0.762
- ET acumulada 5 días (incluye día satelital): r = 0.588, rho = 0.524
- ET acumulada 7 días (incluye día satelital): r = 0.395, rho = 0.262

## Robustez con muestra pequeña

El análisis de robustez se realizó sobre el modelo ET diaria (mismo día) ~ SAVI. En leave-one-out, la correlación varió entre r = 0.850 y r = 0.930, mientras que R² osciló entre 0.722 y 0.866. La fecha más influyente fue 2025-12-18, pero incluso en ese caso el cambio absoluto máximo fue moderado (ΔR² = 0.088; Δr = 0.050).

El bootstrap mantuvo una pendiente positiva media de 5.126, con intervalo percentil 95% entre 3.656 y 6.950. Para R², la media bootstrap fue 0.796 y el intervalo percentil 95% se ubicó entre 0.430 y 0.983. En términos de correlación, el remuestreo produjo un valor medio de r = 0.887, con intervalo percentil 95% entre 0.651 y 0.992.

El test de permutación mostró que la correlación observada (|r| = 0.900) excedió el promedio de la distribución nula (|r| = 0.314) y también su percentil 95 (0.718), con un valor p empírico bilateral de 0.0057.

## Interpretación prudente

En conjunto, estos resultados indican que la asociación observada entre SAVI y la ET diaria de estación fue consistente dentro de la muestra disponible y no parece depender de una única observación extrema. Sin embargo, la amplitud de los intervalos bootstrap confirma que la magnitud exacta del efecto sigue siendo incierta, por lo que el resultado debe interpretarse como evidencia exploratoria y no como una validación definitiva de estimación remota de ET.
