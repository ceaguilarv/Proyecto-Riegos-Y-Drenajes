from __future__ import annotations

from pathlib import Path
import json
import warnings

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point


# ============================================================
# 12_extract_landsat_lst_buffer_timeseries.py
# Extrae serie temporal térmica Landsat 8/9 sobre buffer ROI.
# NOTA CIENTÍFICA:
# Este script NO calcula ET satelital. Extrae una variable térmica
# remota (LST) potencialmente más cercana al balance energético que
# los proxies espectrales, pero sigue siendo una capa intermedia.
# ============================================================


# =========================
# Configuración general
# =========================
BASE_DIR = Path(__file__).resolve().parent

INPUT_STATION_DAILY = BASE_DIR / "data" / "processed" / "station_daily_exterior_ready.csv"

OUTPUT_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_VECTOR_DIR = BASE_DIR / "data" / "vectors"
OUTPUT_VECTOR_DIR.mkdir(parents=True, exist_ok=True)

OUT_POINT_GEOJSON = OUTPUT_VECTOR_DIR / "station_point.geojson"
OUT_BUFFER_GEOJSON = OUTPUT_VECTOR_DIR / "station_buffer_300m.geojson"

OUT_LST_TIMESERIES = OUTPUT_DIR / "landsat_lst_roi_timeseries.csv"
OUT_LST_SUMMARY = OUTPUT_DIR / "landsat_lst_roi_summary.csv"

# Coordenadas estación (lat, lon)
STATION_LAT = 4.636146
STATION_LON = -74.088631

# Geometría
BUFFER_METERS = 300
WORKING_CRS_METRIC = "EPSG:9377"

# Fechas
DEFAULT_START = "2025-07-30"
DEFAULT_END = "2026-01-13"

# Calidad
MIN_VALID_PIXEL_PCT = 30.0
REDUCE_SCALE_METERS = 30


# =========================
# Utilidades
# =========================
def ensure_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")


def load_station_dates(path: Path) -> tuple[str, str]:
    """
    Usa la tabla diaria exterior para definir el rango temporal.
    Si no existe, usa el rango por defecto del proyecto.
    """
    if not path.exists():
        warnings.warn(
            f"No se encontró {path}. Se usarán fechas por defecto: "
            f"{DEFAULT_START} a {DEFAULT_END}"
        )
        return DEFAULT_START, DEFAULT_END

    df = pd.read_csv(path)
    if "date" not in df.columns or df.empty:
        warnings.warn(
            f"El archivo {path} no tiene columna 'date' o está vacío. "
            f"Se usarán fechas por defecto."
        )
        return DEFAULT_START, DEFAULT_END

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).copy()

    if df.empty:
        return DEFAULT_START, DEFAULT_END

    start_date = df["date"].min().strftime("%Y-%m-%d")
    end_date = df["date"].max().strftime("%Y-%m-%d")
    return start_date, end_date


def to_featurecollection_from_gdf(gdf: gpd.GeoDataFrame) -> ee.FeatureCollection:
    geojson = json.loads(gdf.to_json())
    features = []
    for feat in geojson["features"]:
        geom = ee.Geometry(feat["geometry"])
        props = feat.get("properties", {})
        features.append(ee.Feature(geom, props))
    return ee.FeatureCollection(features)


# =========================
# Construcción del ROI
# =========================
def build_station_point_gdf(lat: float, lon: float) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame(
        {"name": ["station_point"]},
        geometry=[Point(lon, lat)],
        crs="EPSG:4326",
    )
    return gdf


def build_buffer_gdf(point_gdf: gpd.GeoDataFrame, buffer_meters: float) -> gpd.GeoDataFrame:
    metric = point_gdf.to_crs(WORKING_CRS_METRIC).copy()
    metric["geometry"] = metric.geometry.buffer(buffer_meters)
    buffered = metric.to_crs("EPSG:4326")
    buffered["name"] = f"station_buffer_{int(buffer_meters)}m"
    return buffered


def save_vectors(point_gdf: gpd.GeoDataFrame, buffer_gdf: gpd.GeoDataFrame) -> None:
    point_gdf.to_file(OUT_POINT_GEOJSON, driver="GeoJSON")
    buffer_gdf.to_file(OUT_BUFFER_GEOJSON, driver="GeoJSON")


# =========================
# Earth Engine
# =========================
def init_ee() -> None:
    
    ee.Authenticate(auth_mode='localhost')
    ee.Initialize(project='bamboo-storm-477002-v4')

    print("GEE ok")


def mask_landsat_l2(image: ee.Image) -> ee.Image:
    """
    Enmascara nubes, sombra, cirros, nieve y saturación radiométrica
    usando QA_PIXEL y QA_RADSAT en Landsat Collection 2 Level 2.
    """
    qa_pixel = image.select("QA_PIXEL")
    qa_radsat = image.select("QA_RADSAT")

    mask = (
        qa_pixel.bitwiseAnd(1 << 1).eq(0)  # dilated cloud
        .And(qa_pixel.bitwiseAnd(1 << 2).eq(0))  # cirrus
        .And(qa_pixel.bitwiseAnd(1 << 3).eq(0))  # cloud
        .And(qa_pixel.bitwiseAnd(1 << 4).eq(0))  # cloud shadow
        .And(qa_pixel.bitwiseAnd(1 << 5).eq(0))  # snow
        .And(qa_radsat.eq(0))  # sin saturación radiométrica
    )

    return image.updateMask(mask)


def add_lst_celsius(image: ee.Image) -> ee.Image:
    """
    Convierte ST_B10 (Surface Temperature) a grados Celsius.
    Para Landsat Collection 2 Level 2:
    ST_B10 = DN * 0.00341802 + 149.0  [Kelvin]
    """
    lst_k = image.select("ST_B10").multiply(0.00341802).add(149.0).rename("LST_K")
    lst_c = lst_k.subtract(273.15).rename("LST_C")
    return image.addBands([lst_k, lst_c])


def add_valid_pixel_fraction(image: ee.Image, roi: ee.Geometry) -> ee.Image:
    """
    Calcula el porcentaje de píxeles válidos dentro del ROI
    a partir de la máscara de LST_C.
    """
    lst_mask = image.select("LST_C").mask()

    valid_count = lst_mask.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=roi,
        scale=REDUCE_SCALE_METERS,
        maxPixels=1_000_000,
    ).get("LST_C")

    total_count = ee.Image.constant(1).clip(roi).reduceRegion(
        reducer=ee.Reducer.count(),
        geometry=roi,
        scale=REDUCE_SCALE_METERS,
        maxPixels=1_000_000,
    ).get("constant")

    valid_pct = ee.Number(valid_count).divide(ee.Number(total_count)).multiply(100)

    return image.set({"valid_pixel_pct": valid_pct})


def add_common_metadata(image: ee.Image, sensor_label: str) -> ee.Image:
    return image.set(
        {
            "sensor_label": sensor_label,
            "spacecraft_id": image.get("SPACECRAFT_ID"),
            "wrs_path": image.get("WRS_PATH"),
            "wrs_row": image.get("WRS_ROW"),
        }
    )


def build_landsat_collection(
    roi: ee.Geometry,
    start_date: str,
    end_date: str,
) -> ee.ImageCollection:
    l8 = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterDate(start_date, end_date)
        .filterBounds(roi)
        .map(mask_landsat_l2)
        .map(add_lst_celsius)
        .map(lambda img: add_valid_pixel_fraction(img, roi))
        .map(lambda img: add_common_metadata(img, "Landsat-8"))
    )

    l9 = (
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        .filterDate(start_date, end_date)
        .filterBounds(roi)
        .map(mask_landsat_l2)
        .map(add_lst_celsius)
        .map(lambda img: add_valid_pixel_fraction(img, roi))
        .map(lambda img: add_common_metadata(img, "Landsat-9"))
    )

    merged = l8.merge(l9).sort("system:time_start")
    return merged


def reduce_image_to_roi(image: ee.Image, roi: ee.Geometry) -> ee.Feature:
    reducers = (
        ee.Reducer.mean()
        .combine(ee.Reducer.median(), sharedInputs=True)
        .combine(ee.Reducer.stdDev(), sharedInputs=True)
    )

    reduced = image.select(["LST_C", "LST_K"]).reduceRegion(
        reducer=reducers,
        geometry=roi,
        scale=REDUCE_SCALE_METERS,
        maxPixels=1_000_000,
        bestEffort=True,
    )

    feature = ee.Feature(
        None,
        reduced
        .set("image_id", image.id())
        .set("date", ee.Date(image.get("system:time_start")).format("YYYY-MM-dd"))
        .set(
            "datetime_utc",
            ee.Date(image.get("system:time_start")).format("YYYY-MM-dd HH:mm:ss"),
        )
        .set("sensor_label", image.get("sensor_label"))
        .set("spacecraft_id", image.get("spacecraft_id"))
        .set("wrs_path", image.get("wrs_path"))
        .set("wrs_row", image.get("wrs_row"))
        .set("valid_pixel_pct", image.get("valid_pixel_pct"))
    )

    return feature


def featurecollection_to_dataframe(fc: ee.FeatureCollection) -> pd.DataFrame:
    data = fc.getInfo()
    rows = []
    for feat in data["features"]:
        rows.append(feat["properties"])
    return pd.DataFrame(rows)


# =========================
# Limpieza de salidas
# =========================
def clean_timeseries_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    numeric_cols = [
        "valid_pixel_pct",
        "wrs_path",
        "wrs_row",
        "LST_C_mean",
        "LST_C_median",
        "LST_C_stdDev",
        "LST_K_mean",
        "LST_K_median",
        "LST_K_stdDev",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["is_valid_satellite_obs"] = df["valid_pixel_pct"] >= MIN_VALID_PIXEL_PCT

    ordered_cols = [
        "date",
        "datetime_utc",
        "image_id",
        "sensor_label",
        "spacecraft_id",
        "wrs_path",
        "wrs_row",
        "valid_pixel_pct",
        "is_valid_satellite_obs",
        "LST_C_mean",
        "LST_C_median",
        "LST_C_stdDev",
        "LST_K_mean",
        "LST_K_median",
        "LST_K_stdDev",
    ]
    ordered_cols = [c for c in ordered_cols if c in df.columns]

    return df[ordered_cols].sort_values("date").reset_index(drop=True)


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            {
                "metric": [
                    "n_images",
                    "n_valid_images",
                    "mean_valid_pixel_pct",
                    "mean_lst_c",
                    "median_lst_c",
                    "std_lst_c",
                ],
                "value": [0, 0, np.nan, np.nan, np.nan, np.nan],
            }
        )

    valid = df[df["is_valid_satellite_obs"]].copy()

    return pd.DataFrame(
        {
            "metric": [
                "n_images",
                "n_valid_images",
                "mean_valid_pixel_pct",
                "mean_lst_c",
                "median_lst_c",
                "std_lst_c",
            ],
            "value": [
                len(df),
                len(valid),
                df["valid_pixel_pct"].mean(),
                valid["LST_C_mean"].mean() if not valid.empty else np.nan,
                valid["LST_C_median"].median() if not valid.empty else np.nan,
                valid["LST_C_stdDev"].mean() if not valid.empty else np.nan,
            ],
        }
    )


def print_report(df: pd.DataFrame, start_date: str, end_date: str) -> None:
    print("\n=== EXTRACCIÓN LANDSAT 8/9 LST SOBRE BUFFER 300 m ===")
    print(f"Rango temporal:             {start_date} a {end_date}")
    print(f"Imágenes totales:           {len(df)}")

    if not df.empty:
        n_valid = int(df["is_valid_satellite_obs"].sum())
        print(f"Imágenes válidas:           {n_valid}")
        print(f"% píxeles válidos medio:    {df['valid_pixel_pct'].mean():.2f}")

        if "LST_C_mean" in df.columns:
            print(f"LST_C_mean:".ljust(28), f"{df['LST_C_mean'].mean():.2f}")
        if "LST_C_median" in df.columns:
            print(f"LST_C_median:".ljust(28), f"{df['LST_C_median'].median():.2f}")
        if "LST_C_stdDev" in df.columns:
            print(f"LST_C_stdDev:".ljust(28), f"{df['LST_C_stdDev'].mean():.2f}")

        print("\nPrimeras 10 observaciones:")
        show_cols = [
            "date",
            "sensor_label",
            "valid_pixel_pct",
            "is_valid_satellite_obs",
            "LST_C_mean",
            "LST_C_median",
            "LST_C_stdDev",
        ]
        show_cols = [c for c in show_cols if c in df.columns]
        print(df[show_cols].head(10).to_string(index=False))


# =========================
# Main
# =========================
def main() -> None:
    start_date, end_date = load_station_dates(INPUT_STATION_DAILY)

    # 1. Crear punto y buffer
    point_gdf = build_station_point_gdf(STATION_LAT, STATION_LON)
    buffer_gdf = build_buffer_gdf(point_gdf, BUFFER_METERS)

    # 2. Guardar geometrías para control visual en QGIS
    save_vectors(point_gdf, buffer_gdf)

    # 3. Inicializar Earth Engine
    init_ee()

    # 4. Convertir ROI a Earth Engine
    roi_fc = to_featurecollection_from_gdf(buffer_gdf)
    roi_geom = roi_fc.geometry()

    # 5. Construir colección Landsat 8/9
    landsat = build_landsat_collection(roi_geom, start_date, end_date)

    # 6. Reducir cada imagen al buffer
    features = landsat.map(lambda img: reduce_image_to_roi(img, roi_geom))
    table = featurecollection_to_dataframe(ee.FeatureCollection(features))
    table = clean_timeseries_table(table)

    # 7. Exportar resultados
    table.to_csv(OUT_LST_TIMESERIES, index=False, encoding="utf-8")
    summary = build_summary(table)
    summary.to_csv(OUT_LST_SUMMARY, index=False, encoding="utf-8")

    # 8. Reporte
    print_report(table, start_date, end_date)

    print("\nArchivos generados:")
    print(f"- {OUT_POINT_GEOJSON}")
    print(f"- {OUT_BUFFER_GEOJSON}")
    print(f"- {OUT_LST_TIMESERIES}")
    print(f"- {OUT_LST_SUMMARY}")


if __name__ == "__main__":
    main()