import json

import geopandas as gpd
import pyproj

OSM_RAILWAYS_FILENAME = "~/Downloads/openstreetmap-ND/gis_osm_railways_free_1.shp"

NORTH_DAKOTA_LONGITUDE = -100.437012
NORTH_DAKOTA_LATITUDE = 47.650589

crs_dist = pyproj.CRS(
    proj="aeqd",
    ellps="WGS84",
    datum="WGS84",
    lon_0=NORTH_DAKOTA_LONGITUDE,
    lat_0=NORTH_DAKOTA_LATITUDE,
    units="m",
)
crs_latlon = pyproj.CRS("EPSG:4326")

# read the shapefile and simplify the LineStrings with a tolerance of 10 meters
railways = gpd.read_file(OSM_RAILWAYS_FILENAME).to_crs(crs_dist)
railways["geometry"] = railways["geometry"].simplify(tolerance=10)  # 10 meters lossy
railways = railways.to_crs(crs_latlon)
railways["name"] = railways["name"].fillna("")

railways[["name", "geometry"]].to_file("public/osm-railways.geojson")

class RoundingFloat(float):
    __repr__ = staticmethod(lambda x: f"{x:.5f}")

json.encoder.c_make_encoder = None
json.encoder.float = RoundingFloat

reread = json.load(open("public/osm-railways.geojson"))
json.dump(reread, open("public/osm-railways.geojson", "w"))
