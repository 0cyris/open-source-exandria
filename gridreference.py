import geopandas as gpd
from shapely.geometry import Point

# === CONFIGURATION ===
DATUM_LON = 3.6577277  # Whitestone (Sun Tree)
DATUM_LAT = 8.6795618
CUSTOM_CRS = f"+proj=tmerc +lat_0={DATUM_LAT} +lon_0={DATUM_LON} +k=1 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs"

MGRS_LETTERS = [chr(i) for i in range(65, 91) if chr(i) not in ['I', 'O']]
ORIGIN_INDEX = 12  # NN = 12,12

# GZD config (each GZD is 600 km wide × 800 km tall)
GZD_ZONE_WIDTH = 600_000
GZD_ZONE_HEIGHT = 800_000
GZD_BANDS = 'CDEFGHJKLMNPQRSTUVWX'  # 20 bands, 8° steps

# === FUNCTIONS ===
def encode_zone(dx, dy):
    ix = (ORIGIN_INDEX + dx) % len(MGRS_LETTERS)
    iy = (ORIGIN_INDEX + dy) % len(MGRS_LETTERS)
    return f"{MGRS_LETTERS[iy]}{MGRS_LETTERS[ix]}"

def encode_subgrid(x, y, precision=1):
    factor = 100_000 // precision
    sx = int((x % 100_000) // precision)
    sy = int((y % 100_000) // precision)
    return f"{sx:0{len(str(factor - 1))}} {sy:0{len(str(factor - 1))}}"

def calculate_gzd(lat, lon):
    # Longitude-based zone number, centered on datum
    zone_number = 31 + int((lon - DATUM_LON) // 6)

    # Latitude band letter, ~8° steps from equator
    band_index = int((lat - 0) // 8 + 9)  # Exandria spans maybe 0° to 80°
    if band_index < 0 or band_index >= len(GZD_BANDS):
        return "???"  # Outside defined GZD bands
    band_letter = GZD_BANDS[band_index]

    return f"{zone_number:02d}{band_letter}"

def calculate_mgrs(lat, lon, precision=1):
    pt = gpd.GeoSeries([Point(lon, lat)], crs='EPSG:4326').to_crs(CUSTOM_CRS).iloc[0]
    x, y = pt.x, pt.y
    dx = int((x - 500000) // 100_000)
    dy = int((y - 0) // 100_000)
    zone = encode_zone(dx, dy)
    subgrid = encode_subgrid(x - dx * 100_000, y - dy * 100_000, precision)
    gzd = calculate_gzd(lat, lon)
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
