import pandas as pd
import geopandas as gpd
import pyproj
import pyarrow as pa
import pyarrow.parquet as pq
import awkward as ak
import numpy as np
from tqdm import tqdm

OSM_WATERWAYS_FILENAME = "~/Downloads/openstreetmap-ND/gis_osm_waterways_free_1.shp"
OSM_WATER_FILENAME = "~/Downloads/openstreetmap-ND/gis_osm_water_a_free_1.shp"

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

# OpenStreetMap has two water files: lines (rivers) and polygons (lakes)
waterways = gpd.read_file(OSM_WATERWAYS_FILENAME).to_crs(crs_dist)[
    ["name", "fclass", "geometry"]
].assign(area=0.0)
water = gpd.read_file(OSM_WATER_FILENAME).to_crs(crs_dist).explode("geometry")
print("finished reading files")

# remove the parts of rivers that are in lakes
all_water = water["geometry"].simplify(tolerance=1000).union_all()
print("computed union of all lakes")
waterways_geometry = []
for row in tqdm(waterways.itertuples(), total=len(waterways)):
    waterways_geometry.append(row.geometry.difference(all_water))
waterways["geometry"] = waterways_geometry
waterways = waterways.explode("geometry")
waterways = waterways[waterways["geometry"].apply(lambda x: len(x.coords) != 0)]
print("computed set difference: rivers that are not inside of lakes")

# combine the files: river lines and lake outlines
waterways = pd.concat(
    [
        waterways,
        water["geometry"].boundary.to_frame("geometry").assign(
            name=water["name"],
            fclass="lake",
            area=water["geometry"].area,
        ),
    ]
).explode("geometry")
print("combined data sources")

# simplify everything a tolerance of 20 meters
# (20 meters is 4 times less resolution than roads, so I can take away 2 more bits)
waterways["geometry"] = waterways["geometry"].simplify(tolerance=20)
waterways = waterways.to_crs(crs_latlon)
print("simplified and converted to lat-lon")

waterways = waterways.sort_values(["fclass", "name"])

# zero out the least significant bits, within the established 20 meter tolerance
# so that split-encoding followed by compression can do a better job
longitudes = ak.values_astype(
    ak.Array(
        waterways["geometry"].apply(lambda line: [x for x, y in line.coords]),
    ),
    np.float32,
)
longitudes.layout.content.data[:] = (
    longitudes.layout.content.data.view(np.uint32)
    & ~np.uint32(0b11111)  # 20 meters lossy
).view(np.float32)
print("lossy truncated longitudes")

latitudes = ak.values_astype(
    ak.Array(
        waterways["geometry"].apply(lambda line: [y for x, y in line.coords]),
    ),
    np.float32,
)
latitudes.layout.content.data[:] = (
    latitudes.layout.content.data.view(np.uint32)
    & ~np.uint32(0b11111)  # 20 meters lossy
).view(np.float32)
print("lossy truncated latitudes")

# put everything into an Arrow Table and write to Parquet with all the relevant optimizations
table = pa.table(
    {
        "name": pa.array(waterways["name"]),
        "fclass": pa.array(waterways["fclass"]),
        "area": pa.array(waterways["area"].astype(np.int32), type=pa.int32()),
        "longitude": ak.to_arrow(longitudes, extensionarray=False, list_to32=True),
        "latitude": ak.to_arrow(latitudes, extensionarray=False, list_to32=True),
    }
)
pq.write_table(
    table,
    "public/osm-water.parquet",
    compression="zstd",
    compression_level=22,
    column_encoding={
        "name": "PLAIN",
        "fclass": "PLAIN",
        "area": "PLAIN",
        "longitude": "BYTE_STREAM_SPLIT",
        "latitude": "BYTE_STREAM_SPLIT",
    },
    use_dictionary=False,
)
print("wrote Parquet file: done!")
