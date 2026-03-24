# Borrador de resultados

## Resumen principal

Se analizaron 9 observaciones coincidentes entre la serie diaria de estación y Sentinel-2, distribuidas entre 2025-01-12 y 2025-12-28. El mejor desempeño para la ET del mismo día se observó con SAVI, con una relación relativamente fuerte y positiva frente a la ET de estación (r = 0.814, rho = 0.683, R² = 0.663, RMSE = 0.223 mm d⁻¹, MAE = 0.204 mm d⁻¹, n = 9). La ecuación del ajuste fue: ET = 1.149 + 3.929 × SAVI.

## Párrafo de resultados

En la comparación entre ET diaria de estación y proxies espectrales Sentinel-2, SAVI presentó el mejor ajuste para el mismo día. La correlación de Pearson alcanzó r = 0.814 y el coeficiente de determinación fue R² = 0.663, lo que indica que aproximadamente el 66.3% de la variabilidad observada en la ET diaria quedó capturada por una relación lineal simple con este índice. El error del ajuste fue moderado (RMSE = 0.223 mm d⁻¹; MAE = 0.204 mm d⁻¹), y la pendiente positiva (3.929) sugiere que valores más altos de SAVI tendieron a asociarse con mayores valores de ET de estación en la muestra analizada.

## Comparación entre predictores en ET del mismo día

El orden de desempeño para ET del mismo día fue: 1. SAVI (r = 0.814, R² = 0.663, RMSE = 0.223); 2. NDVI (r = 0.761, R² = 0.580, RMSE = 0.249); 3. EVI (r = 0.742, R² = 0.551, RMSE = 0.257); 4. NDRE (r = 0.682, R² = 0.465, RMSE = 0.281).

## Perfil temporal del mejor predictor

Tomando SAVI como predictor focal, el patrón por escalas temporales fue el siguiente:
- ET diaria (mismo día): r = 0.814, rho = 0.683
- ET media móvil 3 días (incluye día satelital): r = 0.512, rho = 0.533
- ET media móvil 5 días (incluye día satelital): r = 0.411, rho = 0.268
- ET media móvil 7 días (incluye día satelital): r = 0.347, rho = 0.283
- ET acumulada 3 días (incluye día satelital): r = 0.097, rho = 0.333
- ET acumulada 5 días (incluye día satelital): r = -0.038, rho = 0.134
- ET acumulada 7 días (incluye día satelital): r = -0.100, rho = 0.017

## Robustez con muestra pequeña

El análisis de robustez se realizó sobre el modelo ET diaria (mismo día) ~ SAVI. En leave-one-out, la correlación varió entre r = 0.759 y r = 0.863, mientras que R² osciló entre 0.576 y 0.745. La fecha más influyente fue 2025-12-18, pero incluso en ese caso el cambio absoluto máximo fue moderado (ΔR² = 0.087; Δr = 0.055).

El bootstrap mantuvo una pendiente positiva media de 4.064, con intervalo percentil 95% entre 2.224 y 6.006. Para R², la media bootstrap fue 0.672 y el intervalo percentil 95% se ubicó entre 0.305 y 0.912. En términos de correlación, el remuestreo produjo un valor medio de r = 0.812, con intervalo percentil 95% entre 0.552 y 0.955.

El test de permutación mostró que la correlación observada (|r| = 0.814) excedió el promedio de la distribución nula (|r| = 0.287) y también su percentil 95 (0.661), con un valor p empírico bilateral de 0.0087.

## Interpretación prudente

En conjunto, estos resultados indican que la asociación observada entre SAVI y la ET diaria de estación fue consistente dentro de la muestra disponible y no parece depender de una única observación extrema. Sin embargo, la amplitud de los intervalos bootstrap confirma que la magnitud exacta del efecto sigue siendo incierta, por lo que el resultado debe interpretarse como evidencia exploratoria y no como una validación definitiva de estimación remota de ET.
