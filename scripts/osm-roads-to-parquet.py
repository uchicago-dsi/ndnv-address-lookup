import geopandas as gpd
import pyproj
import pyarrow as pa
import pyarrow.parquet as pq
import awkward as ak
import numpy as np

OSM_ROADS_FILENAME = "~/Downloads/openstreetmap-ND/gis_osm_roads_free_1.shp"

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

# read the shapefile and simplify the LineStrings with a tolerance of 5 meters
roads = gpd.read_file(OSM_ROADS_FILENAME).to_crs(crs_dist)
roads["geometry"] = roads["geometry"].simplify(tolerance=5)  # 5 meters lossy
roads = roads.to_crs(crs_latlon)

# some (very few) highways have multiple numbers; make a separate row for each
roads["split_ref"] = roads["ref"].str.split(";")
explode_roads = roads.explode("split_ref")
explode_roads["split_ref"] = explode_roads["split_ref"].str.strip()
# indicate the first in each set of duplicates, so we only draw one
explode_roads["first_ref"] = (
    roads["split_ref"]
    .apply(lambda x: [1] if x is None else [1] + [0] * (len(x) - 1))
    .explode()
)

# sort by string fields so that compression can do a better job
explode_roads = explode_roads.sort_values(["fclass", "name", "split_ref"])

# zero out the least significant bits, within the established 5 meter tolerance
# so that split-encoding followed by compression can do a better job
longitudes = ak.values_astype(
    ak.Array(
        explode_roads["geometry"].apply(lambda line: [x for x, y in line.coords]),
    ),
    np.float32,
)
longitudes.layout.content.data[:] = (
    longitudes.layout.content.data.view(np.uint32) & ~np.uint32(0b11)  # 3 meters lossy
).view(np.float32)

latitudes = ak.values_astype(
    ak.Array(
        explode_roads["geometry"].apply(lambda line: [y for x, y in line.coords]),
    ),
    np.float32,
)
latitudes.layout.content.data[:] = (
    latitudes.layout.content.data.view(np.uint32) & ~np.uint32(0b111)  # 5 meters lossy
).view(np.float32)

# put everything into an Arrow Table and write to Parquet with all the relevant optimizations
table = pa.table(
    {
        "name": pa.array(explode_roads["name"]),
        "fclass": pa.array(explode_roads["fclass"]),
        "ref": pa.array(explode_roads["split_ref"]),
        "draw": pa.array(explode_roads["first_ref"], type=pa.int8()),
        "longitude": ak.to_arrow(longitudes, extensionarray=False, list_to32=True),
        "latitude": ak.to_arrow(latitudes, extensionarray=False, list_to32=True),
    }
)
pq.write_table(
    table,
    "public/osm-roads.parquet",
    compression="zstd",
    compression_level=22,
    column_encoding={
        "name": "PLAIN",
        "fclass": "PLAIN",
        "ref": "PLAIN",
        "draw": "PLAIN",
        "longitude": "BYTE_STREAM_SPLIT",
        "latitude": "BYTE_STREAM_SPLIT",
    },
    use_dictionary=False,
)
