from __future__ import annotations

from pathlib import Path
import json
import warnings

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point


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

OUT_S2_TIMESERIES = OUTPUT_DIR / "sentinel2_roi_timeseries.csv"
OUT_S2_SUMMARY = OUTPUT_DIR / "sentinel2_roi_summary.csv"

# Coordenadas estación (lat, lon)
STATION_LAT = 4.636146
STATION_LON = -74.088631

# Geometría
BUFFER_METERS = 300
WORKING_CRS_METRIC = "EPSG:9377"  # UTM 18N, adecuado para Bogotá

# Fechas
DEFAULT_START = "2025-07-30"
DEFAULT_END = "2026-01-13"

# Nubes y calidad
MAX_CLOUDY_PIXEL_PERCENTAGE = 80
MIN_VALID_PIXEL_PCT = 30.0
REDUCE_SCALE_METERS = 10


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
    buffered["name"] = "station_buffer_300m"
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
  

def mask_s2_sr(image: ee.Image) -> ee.Image:
    """
    Enmascarado usando SCL + QA60.
    """
    scl = image.select("SCL")
    qa60 = image.select("QA60")

    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11

    qa_mask = (
        qa60.bitwiseAnd(cloud_bit_mask).eq(0)
        .And(qa60.bitwiseAnd(cirrus_bit_mask).eq(0))
    )

    scl_mask = (
        scl.neq(3)   # cloud shadow
        .And(scl.neq(8))   # cloud medium probability
        .And(scl.neq(9))   # cloud high probability
        .And(scl.neq(10))  # thin cirrus
        .And(scl.neq(11))  # snow/ice
    )

    return image.updateMask(qa_mask).updateMask(scl_mask)


def add_spectral_indices(image: ee.Image) -> ee.Image:
    """
    Calcula índices espectrales sobre Sentinel-2 SR.
    Las bandas SR vienen escaladas; por eso se multiplican por 0.0001.
    """
    scaled = image.select(["B2", "B4", "B5", "B8"]).multiply(0.0001)

    blue = scaled.select("B2")
    red = scaled.select("B4")
    rededge = scaled.select("B5")
    nir = scaled.select("B8")

    ndvi = nir.subtract(red).divide(nir.add(red)).rename("NDVI")

    evi = (
        nir.subtract(red)
        .multiply(2.5)
        .divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1))
        .rename("EVI")
    )

    L = 0.5
    savi = (
        nir.subtract(red)
        .multiply(1 + L)
        .divide(nir.add(red).add(L))
        .rename("SAVI")
    )

    ndre = nir.subtract(rededge).divide(nir.add(rededge)).rename("NDRE")

    return image.addBands([ndvi, evi, savi, ndre])


def add_valid_pixel_fraction(image: ee.Image, roi: ee.Geometry) -> ee.Image:
    """
    Calcula el porcentaje de píxeles válidos dentro del ROI
    a partir de la máscara de NDVI.
    """
    ndvi_mask = image.select("NDVI").mask()

    valid_count = ndvi_mask.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=roi,
        scale=REDUCE_SCALE_METERS,
        maxPixels=1_000_000,
    ).get("NDVI")

    total_count = ee.Image.constant(1).clip(roi).reduceRegion(
        reducer=ee.Reducer.count(),
        geometry=roi,
        scale=REDUCE_SCALE_METERS,
        maxPixels=1_000_000,
    ).get("constant")

    valid_pct = ee.Number(valid_count).divide(ee.Number(total_count)).multiply(100)

    return image.set({"valid_pixel_pct": valid_pct})


def build_s2_collection(
    roi: ee.Geometry,
    start_date: str,
    end_date: str,
) -> ee.ImageCollection:
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start_date, end_date)
        .filterBounds(roi)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", MAX_CLOUDY_PIXEL_PERCENTAGE))
        .map(mask_s2_sr)
        .map(add_spectral_indices)
        .map(lambda img: add_valid_pixel_fraction(img, roi))
    )
    return collection


def reduce_image_to_roi(image: ee.Image, roi: ee.Geometry) -> ee.Feature:
    reducers = (
        ee.Reducer.mean()
        .combine(ee.Reducer.median(), sharedInputs=True)
        .combine(ee.Reducer.stdDev(), sharedInputs=True)
    )

    reduced = image.select(["NDVI", "EVI", "SAVI", "NDRE"]).reduceRegion(
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
        .set("cloudy_pixel_percentage", image.get("CLOUDY_PIXEL_PERCENTAGE"))
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
        "cloudy_pixel_percentage",
        "valid_pixel_pct",
        "NDVI_mean", "NDVI_median", "NDVI_stdDev",
        "EVI_mean", "EVI_median", "EVI_stdDev",
        "SAVI_mean", "SAVI_median", "SAVI_stdDev",
        "NDRE_mean", "NDRE_median", "NDRE_stdDev",
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
        "cloudy_pixel_percentage",
        "valid_pixel_pct",
        "is_valid_satellite_obs",
        "NDVI_mean", "NDVI_median", "NDVI_stdDev",
        "EVI_mean", "EVI_median", "EVI_stdDev",
        "SAVI_mean", "SAVI_median", "SAVI_stdDev",
        "NDRE_mean", "NDRE_median", "NDRE_stdDev",
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
                    "mean_ndvi",
                    "mean_evi",
                    "mean_savi",
                    "mean_ndre",
                ],
                "value": [0, 0, np.nan, np.nan, np.nan, np.nan, np.nan],
            }
        )

    valid = df[df["is_valid_satellite_obs"]].copy()

    return pd.DataFrame(
        {
            "metric": [
                "n_images",
                "n_valid_images",
                "mean_valid_pixel_pct",
                "mean_ndvi",
                "mean_evi",
                "mean_savi",
                "mean_ndre",
            ],
            "value": [
                len(df),
                len(valid),
                df["valid_pixel_pct"].mean(),
                valid["NDVI_mean"].mean() if not valid.empty else np.nan,
                valid["EVI_mean"].mean() if not valid.empty else np.nan,
                valid["SAVI_mean"].mean() if not valid.empty else np.nan,
                valid["NDRE_mean"].mean() if not valid.empty else np.nan,
            ],
        }
    )


def print_report(df: pd.DataFrame, start_date: str, end_date: str) -> None:
    print("\n=== EXTRACCIÓN SENTINEL-2 SOBRE BUFFER 300 m ===")
    print(f"Rango temporal:             {start_date} a {end_date}")
    print(f"Imágenes totales:           {len(df)}")

    if not df.empty:
        n_valid = int(df["is_valid_satellite_obs"].sum())
        print(f"Imágenes válidas:           {n_valid}")
        print(f"% píxeles válidos medio:    {df['valid_pixel_pct'].mean():.2f}")

        for var in ["NDVI_mean", "EVI_mean", "SAVI_mean", "NDRE_mean"]:
            if var in df.columns:
                print(f"{var}:".ljust(28), f"{df[var].mean():.4f}")

        print("\nPrimeras 10 observaciones:")
        show_cols = [
            "date",
            "cloudy_pixel_percentage",
            "valid_pixel_pct",
            "is_valid_satellite_obs",
            "NDVI_mean",
            "EVI_mean",
            "SAVI_mean",
            "NDRE_mean",
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

    # 5. Construir colección Sentinel-2
    s2 = build_s2_collection(roi_geom, start_date, end_date)

    # 6. Reducir cada imagen al buffer
    features = s2.map(lambda img: reduce_image_to_roi(img, roi_geom))
    table = featurecollection_to_dataframe(ee.FeatureCollection(features))
    table = clean_timeseries_table(table)

    # 7. Exportar resultados
    table.to_csv(OUT_S2_TIMESERIES, index=False, encoding="utf-8")
    summary = build_summary(table)
    summary.to_csv(OUT_S2_SUMMARY, index=False, encoding="utf-8")

    # 8. Reporte
    print_report(table, start_date, end_date)

    print("\nArchivos generados:")
    print(f"- {OUT_POINT_GEOJSON}")
    print(f"- {OUT_BUFFER_GEOJSON}")
    print(f"- {OUT_S2_TIMESERIES}")
    print(f"- {OUT_S2_SUMMARY}")


if __name__ == "__main__":
    main()