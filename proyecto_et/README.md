# Proyecto Riegos y Drenajes

## Integración de datos meteorológicos de superficie y Sentinel-2 para la estimación exploratoria de Kc dinámico y ETc espacial en una cobertura de pasturas

Repositorio del proyecto final de Riegos y Drenajes orientado a integrar datos de estación meteorológica, Sentinel-2 y Landsat/LST para analizar la relación entre evapotranspiración de estación, proxies espectrales y una aproximación espacial de Kc dinámico y ETc.

## Autores

* Carlos Esteban Aguilar Vargas
* Augusto José Niño

## Descripción general

El proyecto evalúa la viabilidad de construir una aproximación exploratoria de coeficiente de cultivo dinámico (`Kc_dynamic`) y evapotranspiración del cultivo espacializada (`ETc_dynamic`) a partir de la integración entre:

* datos meteorológicos de superficie;
* índices espectrales Sentinel-2;
* temperatura superficial terrestre Landsat/LST como diagnóstico complementario;
* delimitación de un área de interés de pasturas;
* exclusión de construcciones y superficies duras para reducir mezcla espectral.

El objetivo central no es calcular evapotranspiración satelital física directa, sino proponer una ruta metodológica reproducible para espacializar una señal puntual de estación meteorológica mediante un Kc dinámico derivado de información espectral.

## Repositorio

Repositorio público:

https://github.com/ceaguilarv/Proyecto-Riegos-Y-Drenajes

## Estructura general del proyecto

```text
proyecto_et/
├── data/
│   ├── article_figures/
│   │   ├── maps_qgis/
│   │   │   ├── exports_png/
│   │   │   └── qgis_project/
│   ├── article_tables/
│   ├── article_text/
│   ├── processed/
│   ├── rasters/
│   │   └── kc_etc/
│   │       ├── raw_from_drive/
│   │       ├── masked/
│   │       └── stats/
│   └── vectors/
├── outputs/
├── 00_parse_station_excel.py
├── 01_qc_meteo.py
├── 02_extract_daily_et_station.py
├── 03_prepare_station_exterior_for_satellite.py
├── 04_extract_sentinel2_buffer_timeseries.py
├── 05_prepare_sentinel2_daily_series.py
├── 06_merge_station_sentinel_timeseries.py
├── 07_run_station_sentinel_regressions.py
├── 08_make_article_tables.py
├── 09_make_article_figures.py
├── 10_run_small_sample_robustness.py
├── 11_write_results_narrative_support.py
├── 12_extract_landsat_lst_buffer_timeseries.py
├── 13_prepare_landsat_daily_series.py
├── 14_merge_station_landsat_timeseries.py
├── 15_make_landsat_diagnostics.py
├── 16_final_project_audit.py
├── 17_make_final_outputs_index.py
├── 18_build_dynamic_kc_maps.py
├── 19_evaluate_dynamic_kc_etc.py
├── 20_update_final_outputs_with_kc.py
├── 21_mask_kc_rasters_with_aoi.py
├── proyecto_riegos_final_articulo.qmd
├── referencias.bib
└── README.md
```

## Flujo metodológico

El procesamiento se organiza en cinco bloques principales.

### 1. Estación meteorológica

Scripts:

```text
00_parse_station_excel.py
01_qc_meteo.py
02_extract_daily_et_station.py
03_prepare_station_exterior_for_satellite.py
```

Estos scripts depuran la base meteorológica, corrigen fechas, consolidan registros diarios y preparan la serie exterior usada para cruces con datos satelitales.

La serie final corregida contiene:

* 158 días diarios;
* 143 días válidos para análisis;
* rango temporal: 2025-07-30 a 2026-01-13.

### 2. Sentinel-2

Scripts:

```text
04_extract_sentinel2_buffer_timeseries.py
05_prepare_sentinel2_daily_series.py
06_merge_station_sentinel_timeseries.py
07_run_station_sentinel_regressions.py
```

Esta rama calcula índices espectrales Sentinel-2 y los cruza con la ET diaria de estación.

Índices evaluados:

* NDVI;
* EVI;
* SAVI;
* NDRE.

Resultado principal corregido:

```text
ET diaria de estación ~ SAVI_mean
n = 8
r = 0.900
R² = 0.810
RMSE = 0.173 mm/día
```

El resultado se interpreta como asociación exploratoria entre ET de estación y un proxy espectral, no como validación directa de ET satelital.

### 3. Landsat/LST

Scripts:

```text
12_extract_landsat_lst_buffer_timeseries.py
13_prepare_landsat_daily_series.py
14_merge_station_landsat_timeseries.py
15_make_landsat_diagnostics.py
```

Esta rama extrae temperatura superficial terrestre (`LST`) desde Landsat 8/9 Collection 2 Level 2.

Resultado diagnóstico:

* 18 escenas Landsat disponibles sobre el ROI;
* 4 escenas válidas;
* 4 coincidencias estación-LST;
* rango analysis-ready: 2025-11-07 a 2025-12-17.

Debido al bajo número de coincidencias válidas, Landsat/LST se conserva como diagnóstico térmico complementario y no se usa para regresiones robustas.

### 4. Kc dinámico y ETc espacial

Scripts:

```text
18_build_dynamic_kc_maps.py
19_evaluate_dynamic_kc_etc.py
21_mask_kc_rasters_with_aoi.py
```

Esta rama construye un Kc dinámico exploratorio a partir de Sentinel-2:

```text
Kc_dynamic = Kc_min + VI_norm × (Kc_max - Kc_min)
```

donde:

```text
Kc_min = 0.70
Kc_max = 1.05
```

El índice principal es SAVI y NDVI se usa como comparación metodológica.

Luego se calcula:

```text
ETc_dynamic = ET_base_estación × Kc_dynamic
```

El producto final se generó sobre un AOI limpio de pasturas, excluyendo construcciones y superficies duras.

Resultados sobre AOI limpio:

```text
Kc_SAVI_mean: 0.819 – 0.986
ETc_SAVI_mean: 1.475 – 2.851 mm/día
```

El producto se interpreta como una espacialización exploratoria de la ET de estación modulada por vigor/cobertura vegetal.

### 5. Tablas, figuras y auditoría

Scripts:

```text
08_make_article_tables.py
09_make_article_figures.py
10_run_small_sample_robustness.py
11_write_results_narrative_support.py
16_final_project_audit.py
17_make_final_outputs_index.py
20_update_final_outputs_with_kc.py
```

Estos scripts generan tablas, figuras, textos de soporte, auditoría final y un índice de salidas para el informe.

## Mapas finales

Los mapas finales exportados desde QGIS se ubican en:

```text
data/article_figures/maps_qgis/exports_png/
```

Mapas principales:

```text
fig_map01_localizacion_area_estudio.png
fig_map02_aoi_limpio_exclusiones.png
fig_map03_kc_savi_multitemporal.png
fig_map04_etc_savi_multitemporal.png
```

Estos mapas muestran:

1. localización del área de estudio;
2. refinamiento espacial del AOI y exclusión de construcciones;
3. variación multitemporal del Kc dinámico basado en SAVI;
4. ETc espacial multitemporal basada en Kc dinámico.

## Requisitos generales

El proyecto fue desarrollado con:

* Python;
* pandas;
* geopandas;
* numpy;
* matplotlib;
* rasterio;
* shapely;
* Google Earth Engine Python API;
* QGIS;
* Quarto.

Instalación mínima sugerida:

```bash
pip install pandas geopandas numpy matplotlib rasterio shapely earthengine-api openpyxl
```

También se requiere autenticación de Google Earth Engine:

```bash
earthengine authenticate
```

o mediante el flujo usado por los scripts:

```python
ee.Authenticate(auth_mode="localhost")
```

## Ejecución del flujo principal

Desde la raíz del proyecto:

```bash
cd /home/rstudio/work/proyecto_et
```

Ejecutar en orden:

```bash
python 00_parse_station_excel.py
python 01_qc_meteo.py
python 02_extract_daily_et_station.py
python 03_prepare_station_exterior_for_satellite.py

python 04_extract_sentinel2_buffer_timeseries.py
python 05_prepare_sentinel2_daily_series.py
python 06_merge_station_sentinel_timeseries.py
python 07_run_station_sentinel_regressions.py

python 08_make_article_tables.py
python 09_make_article_figures.py
python 10_run_small_sample_robustness.py
python 11_write_results_narrative_support.py

python 12_extract_landsat_lst_buffer_timeseries.py
python 13_prepare_landsat_daily_series.py
python 14_merge_station_landsat_timeseries.py
python 15_make_landsat_diagnostics.py

python 18_build_dynamic_kc_maps.py
python 19_evaluate_dynamic_kc_etc.py
python 21_mask_kc_rasters_with_aoi.py

python 16_final_project_audit.py
python 17_make_final_outputs_index.py
python 20_update_final_outputs_with_kc.py
```

## Renderizado del informe

El informe final se encuentra en formato Quarto:

```text
proyecto_riegos_final_articulo.qmd
```

Renderizar a HTML:

```bash
quarto render proyecto_riegos_final_articulo.qmd --to html
```

Renderizar a PDF:

```bash
quarto render proyecto_riegos_final_articulo.qmd --to pdf
```

## Resultados principales

### Sentinel-2

El mejor predictor espectral para la ET diaria de estación fue SAVI:

```text
ET diaria = 0.773 + 5.137 × SAVI
n = 8
r = 0.900
R² = 0.810
RMSE = 0.173 mm/día
```

### Kc dinámico

Sobre el AOI limpio de pasturas, el Kc dinámico basado en SAVI presentó:

```text
Kc_SAVI_mean: 0.819 – 0.986
ETc_SAVI_mean: 1.475 – 2.851 mm/día
```

### Landsat/LST

La rama térmica Landsat/LST quedó limitada por baja disponibilidad de observaciones válidas:

```text
18 escenas Landsat
4 escenas válidas
4 coincidencias estación-LST
```

Por esta razón se reporta como diagnóstico complementario y no como modelo estadístico.

## Limitaciones

El método es viable y reproducible, pero su robustez depende de:

* disponibilidad de imágenes Sentinel-2 libres de nubes;
* calidad y continuidad de la estación meteorológica;
* coincidencia temporal entre estación y satélite;
* adecuada delimitación del AOI;
* exclusión de construcciones y superficies no vegetadas;
* una serie temporal más amplia para validar el comportamiento observado.

El Kc dinámico generado no debe interpretarse como Kc calibrado universal, sino como un coeficiente relativo y exploratorio para el sitio y periodo de análisis.

## Ciencia abierta

Este repositorio se publica bajo un enfoque de ciencia abierta. Los scripts, insumos procesados, tablas, figuras y documentación metodológica se comparten para facilitar la revisión, trazabilidad y reproducción del flujo de trabajo.

Los datos y productos incluidos deben interpretarse bajo los supuestos metodológicos descritos en el informe y en los scripts. En caso de existir datos sensibles o no redistribuibles, se recomienda publicar versiones procesadas, anonimizadas o acompañadas de metadatos suficientes para reproducir el análisis.

## Cita sugerida

Aguilar Vargas, C. E., & Niño, A. J. (2026). *Integración de datos meteorológicos de superficie y Sentinel-2 para la estimación exploratoria de Kc dinámico y ETc espacial en una cobertura de pasturas*. Proyecto final de Riegos y Drenajes, Universidad Nacional de Colombia.

## Contacto

Repositorio mantenido por Carlos Esteban Aguilar Vargas.
GitHub: https://github.com/ceaguilarv
