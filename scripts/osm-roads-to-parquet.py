import json

import geopandas as gpd
import pyproj
import pyarrow as pa
import pyarrow.parquet as pq
import awkward as ak
import numpy as np

# https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_38_tract.zip
CENSUS_TRACTS_FILENAME = "~/Downloads/tl_2024_38_tract.zip"

# https://download.geofabrik.de/north-america/us/north-dakota.html
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

tracts = gpd.read_file(CENSUS_TRACTS_FILENAME).to_crs(crs_latlon)

roads = gpd.read_file(OSM_ROADS_FILENAME).to_crs(crs_dist)

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
explode_roads["name"] = explode_roads["name"].fillna("")

big_roads = explode_roads.query(
    "fclass in ['motorway', 'trunk', 'primary', 'secondary']"
).copy()
small_roads = explode_roads.query(
    "fclass not in ['motorway', 'trunk', 'primary', 'secondary']"
).copy()

# big roads will be loaded statically, so 5 meter tolerance and 5 decimal digits in GeoJSON
big_roads["geometry"] = big_roads["geometry"].simplify(tolerance=5)  # 5 meters lossy
big_roads = big_roads.to_crs(crs_latlon)
big_roads.assign(
    ref_prefix=big_roads["split_ref"].apply(
        lambda x: "" if x is None or " " not in x else x.split(" ", 1)[0]
    ),
    ref_rest=big_roads["split_ref"].apply(
        lambda x: "" if x is None or " " not in x else x.split(" ", 1)[1]
    ),
    ref_length=big_roads["split_ref"].apply(lambda x: 0 if x is None else len(x)),
    ref_rest_length=big_roads["split_ref"].apply(
        lambda x: 0 if x is None or " " not in x else len(x.split(" ", 1)[1])
    ),
    draw=big_roads["first_ref"].astype(int),
)[
    [
        "name",
        "fclass",
        "ref_prefix",
        "ref_rest",
        "ref_length",
        "ref_rest_length",
        "draw",
        "geometry",
    ]
].to_file(
    "public/osm-big-roads.geojson"
)


class RoundingFloat(float):
    __repr__ = staticmethod(lambda x: f"{x:.5f}")


json.encoder.float = RoundingFloat

with open("public/osm-big-roads.geojson") as file:
    reloaded = json.load(file)
with open("public/osm-big-roads.geojson", "w") as file:
    json.dump(reloaded, file, separators=(",", ":"))

# small roads will be loaded dynamically, so 5 meter tolerance and zero out the least significant bits
small_roads["geometry"] = small_roads["geometry"].simplify(
    tolerance=5
)  # 5 meters lossy
small_roads = small_roads.to_crs(crs_latlon)

small_roads_by_tract = gpd.overlay(small_roads, tracts, how="intersection")
small_roads_by_tract = small_roads_by_tract.explode("geometry")

small_roads_by_tract = small_roads_by_tract.sort_values(
    ["TRACTCE", "fclass", "name", "ref"]
)
sorted_tract = np.asarray(small_roads_by_tract["TRACTCE"])
offsets = (
    [0]
    + (np.nonzero(sorted_tract[1:] != sorted_tract[:-1])[0] + 1).tolist()
    + [len(sorted_tract)]
)
for start, stop in zip(offsets[:-1], offsets[1:]):
    assert (small_roads_by_tract[start:stop]["TRACTCE"] == sorted_tract[start]).all()

# zero out the least significant bits, within the established 5 meter tolerance
# so that split-encoding followed by compression can do a better job
longitudes = ak.values_astype(
    ak.Array(
        small_roads_by_tract["geometry"].apply(
            lambda line: [x for x, y in line.coords]
        ),
    ),
    np.float32,
)
longitudes.layout.content.data[:] = (
    longitudes.layout.content.data.view(np.uint32) & ~np.uint32(0b11)  # 3 meters lossy
).view(np.float32)

latitudes = ak.values_astype(
    ak.Array(
        small_roads_by_tract["geometry"].apply(
            lambda line: [y for x, y in line.coords]
        ),
    ),
    np.float32,
)
latitudes.layout.content.data[:] = (
    latitudes.layout.content.data.view(np.uint32) & ~np.uint32(0b111)  # 5 meters lossy
).view(np.float32)

# put everything into an Arrow Table and write to Parquet with all the relevant optimizations
table = pa.table(
    {
        "name": pa.array(small_roads_by_tract["name"]),
        "fclass": pa.array(small_roads_by_tract["fclass"]),
        "ref": pa.array(small_roads_by_tract["split_ref"]),
        "draw": pa.array(small_roads_by_tract["first_ref"], type=pa.int8()),
        "lon": ak.to_arrow(longitudes, extensionarray=False, list_to32=True),
        "lat": ak.to_arrow(latitudes, extensionarray=False, list_to32=True),
    }
)
outfile = pq.ParquetWriter(
    "public/osm-small-roads.parquet",
    schema=table.schema,
    compression="zstd",
    compression_level=22,
    column_encoding={
        "name": "PLAIN",
        "fclass": "PLAIN",
        "ref": "PLAIN",
        "draw": "PLAIN",
        "lon": "BYTE_STREAM_SPLIT",
        "lat": "BYTE_STREAM_SPLIT",
    },
    use_dictionary=False,
)
for start, stop in zip(offsets[:-1], offsets[1:]):
    for batch in table[start:stop].to_batches():
        outfile.write_batch(batch)
outfile.close()
