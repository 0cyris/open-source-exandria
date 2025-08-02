# PyQGIS script to generate 100km and 10km grids for each GZD tile in Exandria
# Outputs GeoJSON files for compatibility with other Exandria data

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsField, QgsFields, QgsWkbTypes, QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext, QgsVectorFileWriter, QgsRectangle
)
from qgis.PyQt.QtCore import QVariant
import math, os

# === Configuration ===
output_dir = "/home/ocyris/devel/open-source-exandria/Data/OSE/mgrs"  # Change this to your actual path
grid_sizes = [100000, 10000]  # 100 km and 10 km
zone_numbers = range(28, 36)  # Adjust for full Exandria coverage
lat_band_min = -40
lat_band_max = 60

# === Functions ===
def create_tm_crs(zone_number):
    central_meridian = zone_number * 6 - 183
    proj_str = f"+proj=tmerc +lat_0=0 +lon_0={central_meridian} +k=0.9996 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs"
    return QgsCoordinateReferenceSystem.fromProj4(proj_str)

def create_grid(extent, spacing, crs, output_path):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GeoJSON"
    options.fileEncoding = "UTF-8"

    writer = QgsVectorFileWriter.create(
        output_path, fields, QgsWkbTypes.Polygon,
        crs, QgsCoordinateTransformContext(), options
    )
    xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()
    cols = math.ceil((xmax - xmin) / spacing)
    rows = math.ceil((ymax - ymin) / spacing)

    for col in range(cols):
        for row in range(rows):
            x1 = xmin + col * spacing
            y1 = ymin + row * spacing
            rect = QgsRectangle(x1, y1, x1 + spacing, y1 + spacing)
            geom = QgsGeometry.fromRect(rect)
            feat = QgsFeature()
            feat.setGeometry(geom)
            feat.setAttributes([col, row])
            writer.addFeature(feat)
    del writer

# === Main Script ===
fields = QgsFields()
fields.append(QgsField("col", QVariant.Int))
fields.append(QgsField("row", QVariant.Int))

for zone in zone_numbers:
    crs = create_tm_crs(zone)
    zone_folder = os.path.join(output_dir, f"zone_{zone}")
    os.makedirs(zone_folder, exist_ok=True)

    # Define projected extent (approx. 1000 km square centered on UTM origin)
    extent = QgsRectangle(200000, 0, 800000, 1000000)

    for size in grid_sizes:
        out_name = os.path.join(zone_folder, f"grid_{size//1000}km.geojson")
        create_grid(extent, size, crs, out_name)

print("✅ GeoJSON grids created for each GZD zone.")
