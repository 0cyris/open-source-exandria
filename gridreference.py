import geopandas as gpd
import math
import pyproj
from shapely.geometry import Point

# === CONFIGURATION ===
DATUM_LON = 0 #3.6577277  # Whitestone (Sun Tree)
DATUM_LAT = 0 #8.6795618
CUSTOM_CRS = f"+proj=tmerc +lat_0={DATUM_LAT} +lon_0={DATUM_LON} +k=1 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs"

MGRS_LETTERS = [chr(i) for i in range(65, 91) if chr(i) not in ['I', 'O']]
ORIGIN_INDEX = 12  # NN = 12,12

# GZD config (each GZD is 600 km wide × 800 km tall)
GZD_ZONE_WIDTH = 600_000
GZD_ZONE_HEIGHT = 800_000
GZD_BANDS = 'CDEFGHJKLMNPQRSTUVWX'  # 20 bands, 8° steps

# === FUNCTIONS ===
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

def encode_subgrid(easting, northing, spacing=1):
    # Remainder within 100 km square
    sub_easting = math.floor(easting % 100000)
    sub_northing = math.floor(northing % 100000)

    # Truncate to spacing
    e_trunc = sub_easting // spacing
    n_trunc = sub_northing // spacing

    # Determine digit width
    digits = int(round(5 - math.log10(spacing)))
    fmt = f"0{digits}d"

    return f"{format(e_trunc, fmt)} {format(n_trunc, fmt)}"


def calculate_gzd(lat, lon):
    # Determine UTM zone number (1–60)
    zone_number = int((lon + 180) / 6) + 1  # standard 6° zone formula

    # Determine latitude band letter (8° bands labeled C–X, skipping I and O)
    band_index = int((lat + 80) / 8)
    if band_index >= len(GZD_BANDS):  # handle 84°N upper edge case
        band_index = len(GZD_BANDS) - 1
    band_letter = GZD_BANDS[band_index]

    return f"{zone_number:02d}{band_letter}"

def calculate_mgrs(lat, lon, precision=1):
    gzd = calculate_gzd(lat, lon)

    # Step 1: Extract zone number from GZD
    zone_number = int(gzd[:2])
    central_meridian = 3 + (zone_number - 31) * 6  # same logic used in calculate_gzd

    # Step 2: Build local CRS for this GZD
    #local_crs = f"+proj=tmerc +lat_0=0 +lon_0={central_meridian} +k=0.9996 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs"

    # Step 3: Project lat/lon to meters using this zone's CRS
    #pt = gpd.GeoSeries([Point(lon, lat)], crs='EPSG:4326').to_crs(local_crs).iloc[0]
    
    # Define transformer from WGS84 lat/lon (EPSG:4326) to UTM zone 31N (EPSG:32631)
    transformer = pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:326{zone_number}", always_xy=True)
    easting, northing = transformer.transform(lon, lat)
    #print(easting, northing)
# Expected output: ~572355.0 959493.0  (meters in zone 31N)
    x, y = easting, northing

    # Step 4: Derive 100km square offset
    dx = int(x // 100_000)
    dy = int(y // 100_000)
    zone = encode_zone(x, y, zone_number)

    # Step 5: Subgrid
    subgrid = encode_subgrid(x, y, precision)

    return f"{gzd} {zone} {subgrid}"

def load_geojson(path):
    df = gpd.read_file(path)
    return df

def lookup_by_name(df, name, precision=1):
    try:
        match = df[df['Name'].str.lower() == name.lower()]
        if match.empty:
            return f"❌ Location '{name}' not found."
        pt = match.geometry.iloc[0]
        if pt.geom_type != 'Point':
            return "❌ Geometry is not a Point."
        return calculate_mgrs(lat=pt.y, lon=pt.x, precision=precision)
    except Exception as e:
        return f"❌ Location '{name}' not found. {e}"
# === EXAMPLE USAGE ===
if __name__ == "__main__":
    cities = load_geojson("Data/OSE/taldorei_cities.geojson")  # Put your GeoJSON here
    for name in ["Whitestone", "Zephrah", "Terrah","Vesrah","Kymal"]:
        print(f"{name}: {lookup_by_name(cities, name, precision=1)}")
    points = load_geojson("Data/OSE/wildemount_nightguard_pois.geojson")  # Put your GeoJSON here
    for name in ["Black Iris EP Bramble","Iron Hearth EP Bramble"]:
        print(f"{name}: {lookup_by_name(points, name, precision=1)}")
