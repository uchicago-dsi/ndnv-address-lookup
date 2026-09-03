#!/usr/bin/env python3
"""Build the base columns of public/911-addresses.parquet from the ND GIS Hub
NG911 "Site Structure Address Points" layer.

This step used to be unscripted. The recipe here was reverse-engineered from the
April-2025 GeoPackage in Box against the shipped Parquet file and reproduces its
nine base columns exactly (see --verify-against). Run
scripts/step2-analyze-wheretovote.py and scripts/step3-add-wheretovote-to-addresses.py
afterwards to add district / in_wheretovote / polling_places / county_fp.

The Parquet internals are not incidental output. The browser reads only the row
groups whose lon/lat statistics intersect the viewport (see
src/lib/AddressesLayer.svelte), so "one row group per census tract" is what keeps
peak phone memory near 70 MB instead of the ~800 MB an undifferentiated file cost.
Preserve the row-group layout, the sort order, the column encodings and the zstd
level on any change.

Source layer:
  https://gishubdata-ndgov.hub.arcgis.com/datasets/NDGOV::ndgishub-site-structure-address-points
  A ready-made GeoPackage export is available without paging:
  https://hub.arcgis.com/api/download/v1/items/7c825491a88b4c03b22fde12eee38f83/geopackage?redirect=false&layers=0

Census tracts (defines the row groups; keep the vintage stable or every row moves):
  https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_38_tract.zip
"""

import argparse
import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pyogrio

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PATH = REPO_ROOT / "public" / "911-addresses.parquet"
DEFAULT_SOURCE_LIST_PATH = REPO_ROOT / "src" / "data" / "source-list.json"
DEFAULT_TRACTS_PATH = Path("~/Downloads/tl_2024_38_tract.zip").expanduser()
# The 2025-04 export named this layer "Structures_NG911"; the 2026-09 export
# names it "DBO_SiteStructureAddressPoints". Override with --layer.
DEFAULT_LAYER_NAME = "DBO_SiteStructureAddressPoints"

# Sort keys, applied to the *derived* (title-cased) values, with a stable sort.
# Verified: this exact list has zero monotonicity violations across all 206 row
# groups of the shipped file, and `unit` is deliberately not a key.
SORT_KEYS = ["TRACTCE", "muni", "msag", "zip", "src", "street", "num"]

BASE_COLUMNS = ["num", "street", "unit", "muni", "msag", "zip", "src", "lon", "lat"]

# Matches scripts/step3-add-wheretovote-to-addresses.py so the layout survives step 3.
COMPRESSION = "zstd"
COMPRESSION_LEVEL = 22
COLUMN_ENCODING = {
    "num": "PLAIN",
    "street": "PLAIN",
    "unit": "PLAIN",
    "muni": "PLAIN",
    "msag": "PLAIN",
    "zip": "PLAIN",
    "src": "PLAIN",
    "lon": "BYTE_STREAM_SPLIT",
    "lat": "BYTE_STREAM_SPLIT",
}

# `street` casing. A plain str.title() is wrong for 61% of rows, so the exceptions
# matter: directional/agency acronyms stay uppercase, originally-uppercase ordinals
# go lowercase, and all-caps Mc* names get inner capitals. The Mc* rule covers every
# Mc* token in the source, so it is a rule rather than a lookup table.
# Historical SOURCE spellings, so this script can still reproduce older exports
# (the regression check against the April-2025 GeoPackage depends on it). The GIS
# Hub renamed Cass County's value between the 2025-04 and 2026-09 exports; both
# must resolve to the same source-list.json position.
SOURCE_ALIASES = {"casscountynd.gov": "CASS COUNTY 911"}

ORDINAL_RE = re.compile(r"^\d+(ST|ND|RD|TH)$")
KEEP_UPPERCASE = frozenset(["NE", "NW", "SE", "SW", "BIA"])


def title_case_word(word: str) -> str:
    if word in KEEP_UPPERCASE:
        return word
    if ORDINAL_RE.match(word):
        return word.lower()
    if word.isupper() and word.isalpha() and word.startswith("MC") and len(word) > 2:
        return "Mc" + word[2:].capitalize()
    return word.title()


def title_case_street(text: str) -> str:
    # Also normalizes runs of whitespace, which the source contains.
    return " ".join(title_case_word(word) for word in text.split())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "gpkg", type=Path, help="NDGISHUB_Site_Structure_Address_Points.gpkg"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--tracts", type=Path, default=DEFAULT_TRACTS_PATH)
    parser.add_argument("--source-list", type=Path, default=DEFAULT_SOURCE_LIST_PATH)
    parser.add_argument("--layer", default=DEFAULT_LAYER_NAME)
    parser.add_argument(
        "--verify-against",
        type=Path,
        default=None,
        help="Compare the result against a reference Parquet file instead of "
        "writing it (structural equality plus the 9-column value multiset)",
    )
    return parser.parse_args()


def load_source_index(source_list_path: Path) -> dict[str, int]:
    """SOURCE string -> position in src/data/source-list.json.

    Positional, NOT a dense re-code of the values present: the shipped file leaves
    index 43 (SIOUX COUNTY 911) unused because the state has no Sioux County data.
    Rebuilding this as sorted(unique(SOURCE)) would shift every code >= 43 and make
    every popup cite the wrong 911 coordinator.
    """
    records = json.loads(source_list_path.read_text())
    index = {record["src"]: position for position, record in enumerate(records)}
    if len(index) != len(records):
        raise RuntimeError("source-list.json has duplicate 'src' values")
    for old_name, current_name in SOURCE_ALIASES.items():
        if current_name in index:
            index.setdefault(old_name, index[current_name])
    return index


def build_frame(
    gpkg_path: Path,
    tracts_path: Path,
    source_index: dict[str, int],
    layer_name: str,
) -> gpd.GeoDataFrame:
    # Read in file order and never reorder: ties on the sort keys are resolved by
    # the original row order, so a stable sort over the as-read frame is required.
    raw = pyogrio.read_dataframe(gpkg_path, layer=layer_name, use_arrow=True)
    print(f"read {len(raw):,} features from {gpkg_path}", file=sys.stderr)

    wgs84 = raw.to_crs("EPSG:4326")

    num = raw["Add_Number"].fillna(-1).astype("int32")
    address = raw["ADDRESS"].fillna("")
    # Drop the house number (the first whitespace token) when there is one. The
    # component fields are deliberately not used: ADDRESS carries word orders and
    # half-address suffixes that the components do not reproduce.
    without_number = address.str.split(n=1).str[1].fillna("")
    rest = np.where(num.to_numpy() == -1, address.to_numpy(), without_number.to_numpy())

    unknown = sorted(set(raw["SOURCE"].dropna().unique()) - set(source_index))
    if unknown:
        raise RuntimeError(
            f"SOURCE value(s) not in source-list.json: {unknown}. Add them at the END "
            f"of src/data/source-list.json so existing src indexes do not shift."
        )

    # float32 with low mantissa bits cleared, then BYTE_STREAM_SPLIT + zstd. The
    # error budget is ~3 m of longitude and ~5 m of latitude, matching the roads.
    lon = (
        (wgs84.geometry.x.to_numpy().astype(np.float32).view(np.uint32) & ~np.uint32(0b11))
        .view(np.float32)
    )
    lat = (
        (wgs84.geometry.y.to_numpy().astype(np.float32).view(np.uint32) & ~np.uint32(0b111))
        .view(np.float32)
    )

    frame = gpd.GeoDataFrame(
        {
            "num": num.to_numpy(),
            "street": [title_case_street(value) for value in rest],
            "unit": raw["Unit"].fillna("").to_numpy(),
            "muni": raw["Inc_Muni"].fillna("").str.title().to_numpy(),
            "msag": raw["MSAGComm"].fillna("").str.title().to_numpy(),
            "zip": raw["Post_Code"].fillna("").to_numpy(),
            "src": raw["SOURCE"].map(source_index).astype("int8").to_numpy(),
            "lon": lon,
            "lat": lat,
        },
        geometry=gpd.points_from_xy(lon, lat, crs="EPSG:4326"),
    )

    tracts = gpd.read_file(tracts_path).to_crs("EPSG:4326")
    joined = gpd.sjoin(
        frame, tracts[["TRACTCE", "geometry"]], how="left", predicate="within"
    )
    if len(joined) != len(frame):
        raise RuntimeError(
            f"tract join changed the row count ({len(frame):,} -> {len(joined):,}); "
            f"a point fell in two tracts"
        )
    if joined["TRACTCE"].isna().any():
        missing = int(joined["TRACTCE"].isna().sum())
        raise RuntimeError(f"{missing:,} point(s) fell outside every census tract")

    return joined.sort_values(SORT_KEYS, kind="stable")


def to_table(frame: gpd.GeoDataFrame) -> pa.Table:
    return pa.table(
        {
            "num": pa.array(frame["num"].to_numpy(), type=pa.int32()),
            "street": pa.array(frame["street"].to_numpy(), type=pa.string()),
            "unit": pa.array(frame["unit"].to_numpy(), type=pa.string()),
            "muni": pa.array(frame["muni"].to_numpy(), type=pa.string()),
            "msag": pa.array(frame["msag"].to_numpy(), type=pa.string()),
            "zip": pa.array(frame["zip"].to_numpy(), type=pa.string()),
            "src": pa.array(frame["src"].to_numpy(), type=pa.int8()),
            "lon": pa.array(frame["lon"].to_numpy(), type=pa.float32()),
            "lat": pa.array(frame["lat"].to_numpy(), type=pa.float32()),
        }
    )


def row_group_sizes(frame: gpd.GeoDataFrame) -> list[int]:
    """One row group per run of equal TRACTCE, in sorted order."""
    codes = frame["TRACTCE"].to_numpy()
    boundaries = np.flatnonzero(codes[1:] != codes[:-1]) + 1
    edges = [0, *boundaries.tolist(), len(codes)]
    return [stop - start for start, stop in zip(edges[:-1], edges[1:])]


def write_parquet(table: pa.Table, sizes: list[int], output_path: Path) -> None:
    writer = pq.ParquetWriter(
        output_path,
        table.schema,
        compression=COMPRESSION,
        compression_level=COMPRESSION_LEVEL,
        column_encoding=COLUMN_ENCODING,
        use_dictionary=False,
    )
    offset = 0
    for size in sizes:
        writer.write_table(table[offset : offset + size])
        offset += size
    writer.close()


def verify(table: pa.Table, sizes: list[int], reference_path: Path) -> int:
    """Structural + content comparison against a reference file.

    Byte-identity is deliberately not required: the deliverable is written with the
    base environment's pyarrow, which differs from older writers in the `created_by`
    string and a couple of bytes per data page.
    """
    reference = pq.ParquetFile(reference_path)
    meta = reference.metadata
    problems = []

    if meta.num_rows != table.num_rows:
        problems.append(f"rows: {meta.num_rows:,} != {table.num_rows:,}")

    reference_sizes = [
        meta.row_group(i).num_rows for i in range(meta.num_row_groups)
    ]
    if reference_sizes != sizes:
        problems.append(
            f"row groups: reference has {len(reference_sizes)} "
            f"{reference_sizes[:5]}..., built has {len(sizes)} {sizes[:5]}..."
        )
    else:
        print(f"OK   {len(sizes)} row groups, identical row counts", file=sys.stderr)

    reference_table = reference.read()
    for name in BASE_COLUMNS:
        if name not in reference_table.column_names:
            problems.append(f"reference is missing column {name}")
            continue
        got = table.column(name).to_pylist()
        expected = reference_table.column(name).to_pylist()
        if got == expected:
            print(f"OK   {name}: identical in order", file=sys.stderr)
        elif sorted(got, key=repr) == sorted(expected, key=repr):
            problems.append(f"{name}: same multiset but different order")
        else:
            differing = sum(1 for a, b in zip(got, expected) if a != b)
            problems.append(
                f"{name}: {differing:,} of {len(got):,} values differ "
                f"(e.g. {[(a, b) for a, b in zip(got, expected) if a != b][:3]})"
            )

    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    if problems:
        return 1
    print("\nverification passed", file=sys.stderr)
    return 0


def main() -> int:
    args = parse_args()
    source_index = load_source_index(args.source_list)
    frame = build_frame(args.gpkg, args.tracts, source_index, args.layer)
    table = to_table(frame)
    sizes = row_group_sizes(frame)
    print(
        f"{table.num_rows:,} rows in {len(sizes)} row groups "
        f"(min {min(sizes)}, max {max(sizes)})",
        file=sys.stderr,
    )

    if args.verify_against is not None:
        return verify(table, sizes, args.verify_against)

    write_parquet(table, sizes, args.output)
    print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
