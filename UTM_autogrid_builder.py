# PyQGIS script to generate 100km and 10km grids for each GZD tile in Exandria
# Outputs GeoJSON files for compatibility with other Exandria data

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsField, QgsFields, QgsWkbTypes, QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext, QgsVectorFileWriter, QgsRectangle,
    QgsCoordinateTransform, QgsPointXY
)
from qgis.PyQt.QtCore import QVariant
import math, os
from concurrent.futures import ThreadPoolExecutor

# === Configuration ===
output_dir = "/home/ocyris/devel/open-source-exandria/Data/OSE/mgrs"  # Change this to your actual path
grid_sizes = [100000, 10000, 1000]  # 100 km and 10 km
gzd_zones = range(28, 32)  # GZD zones across Exandria (adjust as needed)
lat_min, lat_max = -40.0, 84.0  # MGRS-compatible latitudes
mgrs_letters = [chr(i) for i in range(65, 91) if chr(i) not in ['I', 'O']]
origin_index = 12
utm_origin_x = 500000 # 166000
utm_origin_y = 0
row_chunk = 5000

# === Functions ===
def create_tm_crs(zone_number):
    central_meridian = zone_number * 6 - 183
    proj_str = f"+proj=tmerc +lat_0=0 +lon_0={central_meridian} +k=0.9996 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs"
    return QgsCoordinateReferenceSystem.fromProj4(proj_str)

def compute_projected_extent(zone, crs):
    min_x, max_x = 166000, 834000
    xform = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), crs, QgsProject.instance())
    p_south = xform.transform(QgsPointXY(0, lat_min))
    p_north = xform.transform(QgsPointXY(0, lat_max))
    y_min_proj = min(p_south.y(), p_north.y())
    y_max_proj = max(p_south.y(), p_north.y())
    return QgsRectangle(min_x, y_min_proj, max_x, y_max_proj)

def encode_zone(easting, northing, zone_number):
    # Constants
    COLUMN_LETTERS = [
        'ABCDEFGH',  # zone_number % 3 == 1
        'JKLMNPQR',  # zone_number % 3 == 2
        'STUVWXYZ'   # zone_number % 3 == 0
    ]
    ROW_LETTERS = 'ABCDEFGHJKLMNPQRSTUV'  # 20 letters, skipping I and O

    # Determine column letter (easting)
    col_index = int((easting - 100000) // 100000)
    col_set = COLUMN_LETTERS[(zone_number - 1) % 3]
    col_letter = col_set[col_index % 8]  # wrap every 8

    # Determine row letter (northing)
    northing_mod = northing % 2000000
    row_index = int(northing_mod // 100000)
    if zone_number % 2 == 0:
        row_index = (row_index + 5) % 20  # even zones offset
    else:
        row_index = row_index % 20        # odd zones normal
    row_letter = ROW_LETTERS[row_index]

    return f"{col_letter}{row_letter}"

def encode_subgrid(easting, northing, spacing):
    # Remainder within 100 km square
    sub_easting = int(easting % 100000)
    sub_northing = int(northing % 100000)

    # Truncate to spacing
    e_trunc = sub_easting // spacing
    n_trunc = sub_northing // spacing

    # Determine digit width
    digits = int(round(5 - math.log10(spacing)))
    fmt = f"0{digits}d"

    return f"{format(e_trunc, fmt)} {format(n_trunc, fmt)}"



def encode_zone_old(x, y):
    dx = math.floor((x - utm_origin_x) / 100000)
    dy = math.floor((y - utm_origin_y) / 100000)
    ix = (origin_index + dx) % len(mgrs_letters)
    iy = (origin_index + dy) % len(mgrs_letters)
    return f"{mgrs_letters[ix]}{mgrs_letters[iy]}"

def encode_subgrid_old(x, y, spacing):
    base_x = math.floor((x - utm_origin_x) / 100000) * 100000 + utm_origin_x
    base_y = math.floor((y - utm_origin_y) / 100000) * 100000 + utm_origin_y
    local_x = x - base_x
    local_y = y - base_y
    sx = int(local_x // spacing)
    sy = int(local_y // spacing)
    factor = 100000 // spacing
    return f"{sx:0{len(str(factor - 1))}} {sy:0{len(str(factor - 1))}}"

def create_grid(extent, spacing, crs, zone_number, output_path):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GeoJSON"
    options.fileEncoding = "UTF-8"

    fields = QgsFields()
    fields.append(QgsField("col", QVariant.Int))
    fields.append(QgsField("row", QVariant.Int))
    fields.append(QgsField("grid_ref", QVariant.String))
    fields.append(QgsField("zone", QVariant.String))
    fields.append(QgsField("subgrid", QVariant.String))

    writer = QgsVectorFileWriter.create(
        output_path, fields, QgsWkbTypes.Polygon,
        crs, QgsCoordinateTransformContext(), options
    )

    # Extract raw projected bounds
    xmin, ymin, xmax, ymax = (
        extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()
    )

    # Align lower bounds down to the nearest grid line
    xmin = math.floor((xmin - utm_origin_x) / spacing) * spacing + utm_origin_x
    ymin = math.floor((ymin - utm_origin_y) / spacing) * spacing + utm_origin_y

    # Align upper bounds *downwards* to avoid crossing the UTM zone boundary
    xmax = math.floor((xmax - utm_origin_x) / spacing) * spacing + utm_origin_x
    ymax = math.floor((ymax - utm_origin_y) / spacing) * spacing + utm_origin_y

    # Compute the number of columns and rows (do not add +1, since xmax/ymax now lie on the last cell boundary)
    cols = int((xmax - xmin) / spacing)
    rows = int((ymax - ymin) / spacing)

    for col in range(cols):
        for row in range(rows):
            x1 = xmin + col * spacing
            y1 = ymin + row * spacing
            rect = QgsRectangle(x1, y1, x1 + spacing, y1 + spacing)
            geom = QgsGeometry.fromRect(rect)

            # zone_id must come from the surrounding context (passed to encode_zone)
            zone = encode_zone(x1, y1, zone_number)
            subgrid = encode_subgrid(x1, y1, spacing)
            grid_ref = f"{zone} {subgrid}"

            feat = QgsFeature()
            feat.setGeometry(geom)
            feat.setAttributes([col, row, grid_ref, zone, subgrid])
            writer.addFeature(feat)

    del writer


def create_grid_old(extent, spacing, crs, zone_number, output_path):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GeoJSON"
    options.fileEncoding = "UTF-8"

    fields = QgsFields()
    fields.append(QgsField("col", QVariant.Int))
    fields.append(QgsField("row", QVariant.Int))
    fields.append(QgsField("grid_ref", QVariant.String))
    fields.append(QgsField("zone", QVariant.String))
    fields.append(QgsField("subgrid", QVariant.String))

    writer = QgsVectorFileWriter.create(
        output_path, fields, QgsWkbTypes.Polygon,
        crs, QgsCoordinateTransformContext(), options
    )
    xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()
    xmin = math.floor((xmin - utm_origin_x) / spacing) * spacing + utm_origin_x
    ymin = math.floor(ymin / spacing) * spacing
    xmax = math.ceil((xmax - utm_origin_x) / spacing) * spacing + utm_origin_x
    ymax = math.ceil(ymax / spacing) * spacing
    cols = math.ceil((xmax - xmin) / spacing)
    rows = math.ceil((ymax - ymin) / spacing)

    for col in range(cols):
        for row in range(rows):
            x1 = xmin + col * spacing
            y1 = ymin + row * spacing
            rect = QgsRectangle(x1, y1, x1 + spacing, y1 + spacing)
            geom = QgsGeometry.fromRect(rect)
            zone = encode_zone(x1, y1, zone_number)
            subgrid = encode_subgrid(x1, y1, spacing)
            grid_ref = f"{zone} {subgrid}"
            feat = QgsFeature()
            feat.setGeometry(geom)
            feat.setAttributes([col, row, grid_ref, zone, subgrid])
            writer.addFeature(feat)
    del writer

def create_line_grids(extent, spacing, crs, zone_number, output_path):
    xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()
    xmin = math.floor((xmin - utm_origin_x) / spacing) * spacing + utm_origin_x
    ymin = math.floor(ymin / spacing) * spacing
    xmax = math.ceil((xmax - utm_origin_x) / spacing) * spacing + utm_origin_x
    ymax = math.ceil(ymax / spacing) * spacing

    cols = math.ceil((xmax - xmin) / spacing)
    rows = math.ceil((ymax - ymin) / spacing)

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GeoJSON"
    options.fileEncoding = "UTF-8"

    fields = QgsFields()
    fields.append(QgsField("index", QVariant.Int))
    fields.append(QgsField("grid_ref", QVariant.String))
    fields.append(QgsField("zone", QVariant.String))
    fields.append(QgsField("subgrid", QVariant.String))

    col_chunk = 100
    def write_vertical_chunk(col_start):
        chunk_path = output_path.replace(".geojson", f"_vertical_{col_start // col_chunk:03}.geojson")
        writer_v = QgsVectorFileWriter.create(
            chunk_path, fields, QgsWkbTypes.LineString,
            crs, QgsCoordinateTransformContext(), options
        )
        col_end = min(col_start + col_chunk, cols + 1)
        for i in range(col_start, col_end):
            x = xmin + i * spacing
            sample_interval = 1000
            points = [QgsPointXY(x, y) for y in range(int(ymin), int(ymax) + 1, sample_interval)]
            geom = QgsGeometry.fromPolylineXY(points)
            zone = encode_zone(x, ymin, zone_number)
            subgrid = encode_subgrid(x, ymin, spacing)
            sx = subgrid.split()[0]
            zx = zone[0]
            grid_ref = f"{zx} {sx}" if spacing < 10000 else f"{zone} {subgrid}"
            subgrid = sx
            feat = QgsFeature()
            feat.setGeometry(geom)
            feat.setAttributes([i, grid_ref, zone, subgrid])
            writer_v.addFeature(feat)
        del writer_v

    with ThreadPoolExecutor(max_workers=7) as executor:
        executor.map(write_vertical_chunk, range(0, cols + 1, col_chunk))

    row_chunk = 1000
    def write_chunk(row_start):
        chunk_path = output_path.replace(".geojson", f"_horizontal_{row_start // row_chunk:03}.geojson")
        writer_h = QgsVectorFileWriter.create(
            chunk_path, fields, QgsWkbTypes.LineString,
            crs, QgsCoordinateTransformContext(), options
        )
        row_end = min(row_start + row_chunk, rows + 1)
        for j in range(row_start, row_end):
            y = ymin + j * spacing
            sample_interval = 1000
            points = [QgsPointXY(x, y) for x in range(int(xmin), int(xmax) + 1, sample_interval)]
            geom = QgsGeometry.fromPolylineXY(points)
            zone = encode_zone(xmin, y, zone_number)
            subgrid = encode_subgrid(xmin, y, spacing)
            sy = subgrid.split()[1]
            zy = zone[1]
            subgrid = sy
            grid_ref = f"{zy} {sy}" if spacing < 10000 else f"{zone} {subgrid}"
            feat = QgsFeature()
            feat.setGeometry(geom)
            feat.setAttributes([j, grid_ref, zone, subgrid])
            writer_h.addFeature(feat)
        del writer_h

    with ThreadPoolExecutor(max_workers=7) as executor:
        executor.map(write_chunk, range(0, rows + 1, row_chunk))

for zone in gzd_zones:
    crs = create_tm_crs(zone)
    zone_folder = os.path.join(output_dir, f"zone_{zone}")
    os.makedirs(zone_folder, exist_ok=True)
    extent = compute_projected_extent(zone, crs)
    for size in grid_sizes:
        if size >1000:
            print(f"Grid size {size//1000}km")
            out_name = os.path.join(zone_folder, f"grid_{size//1000}km.geojson")
            create_grid(extent, size, crs, zone, out_name)
        else:
            print(f"Grid size {size}m")
            out_name = os.path.join(zone_folder, f"grid_{size}m.geojson")
            create_line_grids(extent, size, crs, zone, out_name)

print("✅ Auto-computed GeoJSON grids and line overlays for each GZD zone.")
