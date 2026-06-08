# Índice final actualizado de salidas del proyecto

## Resumen

- Archivos registrados: 30
- Archivos existentes: 30
- Archivos faltantes: 0

## Decisión metodológica final

El proyecto queda estructurado en tres ramas: **Sentinel-2 como análisis principal de asociación ET–proxy espectral**, **Kc dinámico/ETc espacial como producto metodológico central**, y **Landsat/LST como diagnóstico térmico complementario**. La rama Kc dinámico responde al objetivo de pasar de una señal puntual de estación a una representación espacial modulada por vigor/cobertura vegetal. Debe interpretarse como Kc exploratorio relativo, no como Kc calibrado universal.

## Archivos recomendados para el informe

### Tabla 1. Mejores modelos Sentinel

- Estado: OK
- Ruta: `data/article_tables/table_01_best_models_article.csv`
- Rol: Tabla principal de resultados Sentinel-2.
- Inclusión: yes
- Nota: Incluye el modelo principal ET diaria ~ SAVI_mean y los mejores modelos por target temporal.

### Tabla 2. Regresiones suplementarias Sentinel

- Estado: OK
- Ruta: `data/article_tables/table_02_all_regressions_supplement.csv`
- Rol: Tabla suplementaria con todas las regresiones simples.
- Inclusión: optional/supplement
- Nota: Útil como anexo o material suplementario; no conviene saturar el cuerpo principal.

### Tabla 3. Correlaciones suplementarias Sentinel

- Estado: OK
- Ruta: `data/article_tables/table_03_all_correlations_supplement.csv`
- Rol: Tabla suplementaria con correlaciones Pearson y Spearman.
- Inclusión: optional/supplement
- Nota: Sirve para mostrar ranking completo de predictores y targets.

### Tabla 4. Descripción del dataset Sentinel

- Estado: OK
- Ruta: `data/article_tables/table_04_dataset_description.csv`
- Rol: Resumen descriptivo del dataset analysis-ready Sentinel.
- Inclusión: yes
- Nota: Ya corregida: date_start y date_end deben aparecer como 2025-08-20 y 2025-12-28.

### Tabla 5. Diagnóstico Landsat/LST

- Estado: OK
- Ruta: `data/article_tables/table_05_landsat_lst_diagnostic.csv`
- Rol: Tabla diagnóstica de disponibilidad y calidad Landsat/LST.
- Inclusión: yes
- Nota: Debe entrar como diagnóstico, no como base de regresión.

### Tabla 6. Auditoría final del proyecto

- Estado: OK
- Ruta: `data/article_tables/table_06_final_project_audit.csv`
- Rol: Tabla maestra de control interno del proyecto.
- Inclusión: optional
- Nota: No necesariamente entra completa al informe; sirve para control y trazabilidad.

### Tabla 8. Resumen Kc dinámico y ETc

- Estado: OK
- Ruta: `data/article_tables/table_08_dynamic_kc_etc_summary.csv`
- Rol: Tabla principal de la rama Kc dinámico.
- Inclusión: yes
- Nota: Resume Kc_min, Kc_max, Kc SAVI medio, ETc SAVI media y métricas de interpretación.

### Tabla 9. Kc dinámico y ETc por fecha

- Estado: OK
- Ruta: `data/article_tables/table_09_dynamic_kc_etc_by_date.csv`
- Rol: Tabla detallada por fecha para Kc y ETc.
- Inclusión: yes
- Nota: Permite reportar la evolución temporal de ET base, Kc SAVI, ETc SAVI, Kc NDVI y ETc NDVI.

### Figura 1. Serie temporal estación-Sentinel

- Estado: OK
- Ruta: `data/article_figures/fig01_station_satellite_timeline.png`
- Rol: Figura principal de contexto temporal.
- Inclusión: yes
- Nota: Muestra ET diaria y fechas Sentinel válidas.

### Figura 10. ET base vs ETc dinámica

- Estado: OK
- Ruta: `data/article_figures/fig10_et_base_vs_etc_dynamic.png`
- Rol: Figura descriptiva de relación ET base–ETc.
- Inclusión: optional
- Nota: Debe interpretarse con cautela porque ETc se construye como ET base multiplicada por Kc.

### Figura 2. Mejor modelo ET ~ SAVI

- Estado: OK
- Ruta: `data/article_figures/fig02_scatter_best_same_day_model.png`
- Rol: Figura principal del resultado Sentinel.
- Inclusión: yes
- Nota: Debe acompañar la Tabla 1.

### Figura 3. Comparación predictores Sentinel

- Estado: OK
- Ruta: `data/article_figures/fig03_scatter_same_day_predictor_grid.png`
- Rol: Comparación visual entre SAVI, NDVI, EVI y NDRE.
- Inclusión: yes
- Nota: Muy útil para justificar que SAVI fue el mejor predictor de ET diaria.

### Figura 4. Ranking modelos por target

- Estado: OK
- Ruta: `data/article_figures/fig04_best_model_ranking.png`
- Rol: Ranking de desempeño por escala temporal.
- Inclusión: optional
- Nota: Puede entrar si hay espacio; si no, dejar como suplementaria.

### Figura 5. Perfil temporal del predictor focal

- Estado: OK
- Ruta: `data/article_figures/fig05_temporal_windows_best_predictor.png`
- Rol: Comparación por ventanas temporales.
- Inclusión: optional
- Nota: Útil para explicar por qué el mismo día fue más fuerte.

### Figura 6. Píxeles válidos Landsat/LST

- Estado: OK
- Ruta: `data/article_figures/fig06_landsat_valid_pixel_pct.png`
- Rol: Diagnóstico de disponibilidad térmica.
- Inclusión: yes
- Nota: Figura clave para justificar por qué no se hacen regresiones Landsat.

### Figura 7. LST vs temperatura del aire

- Estado: OK
- Ruta: `data/article_figures/fig07_landsat_lst_vs_tair.png`
- Rol: Comparación descriptiva térmica.
- Inclusión: yes
- Nota: Sirve para mostrar coherencia física sin inferencia estadística.

### Figura 8. Serie temporal ET base y ETc dinámica

- Estado: OK
- Ruta: `data/article_figures/fig08_dynamic_etc_timeseries.png`
- Rol: Figura principal de la rama ETc espacial.
- Inclusión: yes
- Nota: Compara ET base de estación con ETc dinámica basada en SAVI y NDVI.

### Figura 9. Serie temporal Kc dinámico

- Estado: OK
- Ruta: `data/article_figures/fig09_dynamic_kc_timeseries.png`
- Rol: Figura principal del Kc dinámico.
- Inclusión: yes
- Nota: Muestra la evolución temporal del Kc dinámico basado en SAVI y NDVI.

### Auditoría final automática

- Estado: OK
- Ruta: `data/article_text/final_project_audit_report.md`
- Rol: Resumen ejecutivo interno del estado del proyecto.
- Inclusión: optional
- Nota: Puede alimentar la discusión metodológica.

### Borrador de resultados Sentinel

- Estado: OK
- Ruta: `data/article_text/results_sentences_draft.md`
- Rol: Texto base para sección de resultados Sentinel.
- Inclusión: yes
- Nota: Debe actualizarse con los resultados corregidos n=8.

### Captions de figuras

- Estado: OK
- Ruta: `data/article_text/figure_captions_draft.md`
- Rol: Borrador de leyendas de figuras.
- Inclusión: yes
- Nota: Debe revisar que las cifras correspondan al reprocesamiento corregido.

### Notas de tablas

- Estado: OK
- Ruta: `data/article_text/table_notes_draft.md`
- Rol: Notas metodológicas para tablas.
- Inclusión: yes
- Nota: Útil para el informe final.

### Resultados Kc dinámico y ETc espacial

- Estado: OK
- Ruta: `data/article_text/dynamic_kc_etc_results.md`
- Rol: Texto base para la sección de Kc dinámico.
- Inclusión: yes
- Nota: Debe incluirse porque responde al objetivo más importante del proyecto.

### Resultados diagnósticos Landsat

- Estado: OK
- Ruta: `data/article_text/landsat_diagnostic_results.md`
- Rol: Texto base para sección Landsat/LST.
- Inclusión: yes
- Nota: Debe entrar con lenguaje prudente.

### Robustez Sentinel

- Estado: OK
- Ruta: `data/processed/robustness_summary.csv`
- Rol: Resumen de leave-one-out, bootstrap y permutación.
- Inclusión: yes
- Nota: Debe incluirse en resultados o discusión.

