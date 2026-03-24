# Borrador de notas de tablas

## Tabla 1. Mejores modelos por target de ET

Los modelos se ordenaron por desempeño dentro de cada target usando R² en orden descendente y RMSE en orden ascendente. La columna `equation` resume el ajuste lineal simple entre la ET de estación y el predictor satelital correspondiente. Las etiquetas "mismo día", "media móvil" y "acumulada" se refieren a la escala temporal del target de ET. En las ventanas de 3, 5 y 7 días, la agregación incluye la fecha satelital de observación.

## Tabla 2. Regresiones suplementarias

Se reportan intercepto, pendiente, correlación de Pearson, correlación de Spearman, R², RMSE, MAE y sesgo para todas las combinaciones evaluadas entre ET de estación y predictores Sentinel-2. SAVI fue el mejor predictor para la ET del mismo día en la muestra actual.

## Tabla 3. Correlaciones suplementarias

Las correlaciones resumen la intensidad y dirección de la asociación entre los índices espectrales y los distintos targets de ET. Dado el tamaño muestral reducido, estas métricas deben interpretarse como evidencia exploratoria y complementarse con los análisis de robustez.

## Tabla 4. Descripción del dataset analítico

La tabla resume el número de observaciones útiles, el rango temporal analizado y estadísticas descriptivas de ET e índices espectrales. Si el archivo generado desde el script 08 presenta `date_start` o `date_end` como valores faltantes, conviene corregir ese script o extraer las fechas directamente desde `station_sentinel_analysis_ready.csv`, ya que el problema proviene de la coerción numérica de la columna `value`.
