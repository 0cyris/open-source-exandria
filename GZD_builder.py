# PyQGIS Script to Generate GZD Zones as Polygon Layer (6° wide, 8° tall)
# Matches real-world MGRS style and aligned to Exandria-like lat/lon extent

from qgis.core import (
    QgsProject, QgsVectorFileWriter, QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext, QgsFeature, QgsGeometry,
    QgsRectangle, QgsPointXY, QgsFields, QgsField, QgsWkbTypes
)
from qgis.PyQt.QtCore import QVariant
import os

# === Configuration ===
output_path = "/home/ocyris/devel/open-source-exandria/Data/OSE/mgrs/gzd_index.geojson"
crs_epsg = QgsCoordinateReferenceSystem("EPSG:4326")
lon_start = -180
lon_end = 180
lat_start = -80
lat_end = 84

# === Initialize output ===
fields = QgsFields()
fields.append(QgsField("zone", QVariant.String))
fields.append(QgsField("number", QVariant.Int))
fields.append(QgsField("band", QVariant.String))

options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "GeoJSON"
options.fileEncoding = "UTF-8"

writer = QgsVectorFileWriter.create(
    output_path, fields, QgsWkbTypes.Polygon,
    crs_epsg, QgsCoordinateTransformContext(), options
)

# === Letters used in MGRS band rows ===
band_letters = [chr(c) for c in range(ord('C'), ord('X')+1) if chr(c) not in ['I', 'O']]
band_height = 8
zone_width = 6

# === Build GZD zones ===
for zone_number in range(1, 61):  # 60 longitudinal zones
    for i, band in enumerate(band_letters):
        min_lon = lon_start + (zone_number - 1) * zone_width
        max_lon = min_lon + zone_width
        min_lat = lat_start + i * band_height
        max_lat = min_lat + band_height

        rect = QgsRectangle(min_lon, min_lat, max_lon, max_lat)
        geom = QgsGeometry.fromRect(rect)

        feat = QgsFeature()
        feat.setGeometry(geom)
        feat.setAttributes([
            f"{zone_number}{band}", zone_number, band
        ])
        writer.addFeature(feat)

del writer
print("✅ GZD index layer created as GeoJSON.")
