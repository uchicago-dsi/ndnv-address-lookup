#!/usr/bin/env python3

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


DEFAULT_INPUT_PATH = Path("public/911-addresses.parquet")
DEFAULT_DISTRICTS_PATH = Path("public/legislative-districts-exact.gpkg")

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
    "district": "PLAIN",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Input parquet file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output parquet file (defaults to overwriting the input)",
    )
    parser.add_argument(
        "--districts",
        type=Path,
        default=DEFAULT_DISTRICTS_PATH,
        help="GeoPackage with legislative district polygons",
    )
    return parser.parse_args()


def get_row_group_sizes(parquet_path: Path) -> list[int]:
    parquet_file = pq.ParquetFile(parquet_path)
    metadata = parquet_file.metadata
    return [metadata.row_group(i).num_rows for i in range(metadata.num_row_groups)]


def load_dataframe(parquet_path: Path) -> pd.DataFrame:
    return pd.read_parquet(parquet_path)


def assign_districts(dataframe: pd.DataFrame, districts_path: Path) -> pd.DataFrame:
    districts = gpd.read_file(districts_path)[["district", "geometry"]]
    points = gpd.GeoDataFrame(
        dataframe[["lon", "lat"]].copy(),
        geometry=gpd.points_from_xy(dataframe["lon"], dataframe["lat"]),
        crs=districts.crs,
    )
    joined = gpd.sjoin(points, districts, how="left", predicate="within")

    if joined.index.has_duplicates:
        raise RuntimeError("District join produced duplicate address rows")
    if joined["district"].isna().any():
        missing = int(joined["district"].isna().sum())
        raise RuntimeError(f"District join failed for {missing} addresses")

    dataframe = dataframe.copy()
    dataframe["district"] = joined["district"].astype(str).str.strip().str.ljust(2, " ")
    if (dataframe["district"].str.len() != 2).any():
        raise RuntimeError("District values are not fixed-width after padding")
    return dataframe


def build_output_schema(input_schema: pa.Schema, dataframe: pd.DataFrame) -> pa.Schema:
    fields = list(input_schema)
    if "district" not in input_schema.names:
        fields.append(pa.field("district", pa.string()))
    schema = pa.schema(fields, metadata=input_schema.metadata)
    return schema


def dataframe_to_table(dataframe: pd.DataFrame, schema: pa.Schema) -> pa.Table:
    table = pa.Table.from_pandas(dataframe, schema=schema, preserve_index=False)
    return table.replace_schema_metadata(schema.metadata)


def write_table_with_existing_layout(
    table: pa.Table, row_group_sizes: list[int], output_path: Path
) -> None:
    writer = pq.ParquetWriter(
        output_path,
        schema=table.schema,
        compression=COMPRESSION,
        compression_level=COMPRESSION_LEVEL,
        column_encoding=COLUMN_ENCODING,
        use_dictionary=False,
    )
    try:
        start = 0
        for row_group_size in row_group_sizes:
            stop = start + row_group_size
            for batch in table.slice(start, row_group_size).to_batches():
                writer.write_batch(batch)
            start = stop
    finally:
        writer.close()


def main() -> int:
    args = parse_args()
    input_path = args.input
    output_path = args.output if args.output is not None else input_path

    parquet_file = pq.ParquetFile(input_path)
    input_schema = parquet_file.schema_arrow
    row_group_sizes = get_row_group_sizes(input_path)
    dataframe = load_dataframe(input_path)
    dataframe = assign_districts(dataframe, args.districts)
    schema = build_output_schema(input_schema, dataframe)
    table = dataframe_to_table(dataframe, schema)
    write_table_with_existing_layout(table, row_group_sizes, output_path)

    print(f"Loaded {len(dataframe)} rows from {input_path}")
    print(f"Assigned districts from {args.districts}")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
