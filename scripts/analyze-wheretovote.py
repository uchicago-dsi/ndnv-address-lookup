#!/usr/bin/env python3

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq
from shapely import MultiPoint, voronoi_polygons
from tqdm.auto import tqdm


KEY_VALUE_PAIRS_PATH = (
    Path.home()
    / "Box/dsi-core/11th-hour/ndnv-address-lookup/where-to-vote-2026/fetch-WhereToVote/key-value-pairs.csv"
)
ADDRESSES_PATH = Path("public/911-addresses.parquet")
POLLING_PLACES_PATH = Path("public/polling-places.parquet")
COUNTIES_PATH = Path("public/counties-exact.gpkg")
DISTRICTS_PATH = Path("public/legislative-districts-exact.gpkg")

WHERETOVOTE_POINTS_PATH = Path("wheretovote-points.gpkg")
MISSING_POINTS_PATH = Path("missing-points.gpkg")
POLLING_AREAS_PATH = Path("wheretovote-polling-areas.gpkg")
LEGACY_PRECINCT_AREAS_PATH = Path("wheretovote-precinct-areas.gpkg")

VORONOI_CRS = "EPSG:5070"
DEFAULT_MIN_ADDRESSES = 10

PRECINCT_RE = re.compile(r"^(\d{6,})\s*\((\d{4})\)$")
LEGISLATIVE_RE = re.compile(r"^District\s+0*(\d+)([A-Za-z]?)$")

POLLING_FIELDS = [
    "county",
    "county_number",
    "legislative_district",
    "precinct_number",
    "polling_location",
    "address",
    "city",
    "state",
    "zip_code",
    "polling_hours",
    "county_auditor_phone",
]

ABBREVIATION_EQUIVALENTS = {
    "alley": "aly",
    "aly": "aly",
    "avenue": "ave",
    "ave": "ave",
    "boulevard": "blvd",
    "blvd": "blvd",
    "circle": "cir",
    "cir": "cir",
    "court": "ct",
    "ct": "ct",
    "county": "county",
    "drive": "dr",
    "dr": "dr",
    "expressway": "expy",
    "expy": "expy",
    "highway": "hwy",
    "hwy": "hwy",
    "lane": "ln",
    "ln": "ln",
    "parkway": "pkwy",
    "pkwy": "pkwy",
    "place": "pl",
    "pl": "pl",
    "road": "rd",
    "rd": "rd",
    "route": "rte",
    "rte": "rte",
    "square": "sq",
    "sq": "sq",
    "street": "st",
    "st": "st",
    "terrace": "ter",
    "ter": "ter",
    "trail": "trl",
    "trl": "trl",
    "way": "way",
}


def fail(test: str, **context) -> None:
    lines = [f"FAILED: {test}"]
    for key, value in context.items():
        lines.append(f"{key}: {safe_json(value)}")
    raise RuntimeError("\n".join(lines))


def safe_json(value) -> str:
    return json.dumps(value, ensure_ascii=True, default=str)


def normalize_address_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def normalize_address_tokens(value: str) -> list[str]:
    normalized = normalize_address_text(value)
    tokens = normalized.split(" ")
    return [ABBREVIATION_EQUIVALENTS.get(token, token) for token in tokens if token]


def address_prefix_matches(expected_prefix: str, full_address: str) -> bool:
    expected_tokens = normalize_address_tokens(expected_prefix)
    full_tokens = normalize_address_tokens(full_address)
    return full_tokens[: len(expected_tokens)] == expected_tokens


def abbreviation_summary() -> dict[str, list[str]]:
    grouped = {}
    for variant, canonical in sorted(ABBREVIATION_EQUIVALENTS.items()):
        grouped.setdefault(canonical, []).append(variant)
    return grouped


def stable_color(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    rrggbb = int.from_bytes(digest[:8], "big") % (2**24)
    return f"#ff{rrggbb:06x}"


def read_key_value_pairs() -> pd.DataFrame:
    df = pd.read_csv(
        KEY_VALUE_PAIRS_PATH,
        dtype=str,
        usecols=["index", "num", "zip", "street", "result"],
        keep_default_na=False,
    )
    return df


def read_addresses() -> gpd.GeoDataFrame:
    table = pq.read_table(ADDRESSES_PATH)
    df = table.to_pandas()
    df["num"] = df["num"].astype(str)
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4269",
    )
    return gdf


def validate_index_alignment(
    key_value_pairs: pd.DataFrame, addresses: gpd.GeoDataFrame
) -> pd.Series:
    numeric_index = pd.to_numeric(key_value_pairs["index"], errors="coerce")
    invalid_numeric = numeric_index.isna()
    if invalid_numeric.any():
        row = key_value_pairs.loc[invalid_numeric.idxmax()]
        fail("index is not numeric", row=row.to_dict())

    if (numeric_index < 0).any() or (numeric_index >= len(addresses)).any():
        bad_position = ((numeric_index < 0) | (numeric_index >= len(addresses))).idxmax()
        row = key_value_pairs.loc[bad_position]
        fail(
            "index is out of bounds for 911-addresses.parquet",
            row=row.to_dict(),
            addresses_rows=len(addresses),
        )

    numeric_index = numeric_index.astype(int)
    matched = addresses.iloc[numeric_index.to_numpy()][["num", "zip", "street"]].reset_index(
        drop=False
    )

    mismatch_mask = (
        (matched["index"].astype(str) != key_value_pairs["index"].to_numpy())
        | (matched["num"].astype(str) != key_value_pairs["num"].to_numpy())
        | (matched["zip"].astype(str) != key_value_pairs["zip"].to_numpy())
        | (matched["street"].astype(str) != key_value_pairs["street"].to_numpy())
    )
    if mismatch_mask.any():
        bad_position = mismatch_mask.idxmax()
        fail(
            "key-value-pairs index does not match 911-addresses row",
            key_value_pairs_row=key_value_pairs.iloc[bad_position].to_dict(),
            addresses_row_index=int(matched.iloc[bad_position]["index"]),
            addresses_row=matched.iloc[bad_position].to_dict(),
        )

    return numeric_index


def parse_result_arrays(key_value_pairs: pd.DataFrame) -> tuple[pd.Series, list]:
    valid_mask = []
    parsed_arrays = []
    for result in key_value_pairs["result"]:
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            valid_mask.append(False)
            parsed_arrays.append(None)
            continue

        if isinstance(parsed, list):
            valid_mask.append(True)
            parsed_arrays.append(parsed)
        else:
            valid_mask.append(False)
            parsed_arrays.append(None)

    return pd.Series(valid_mask, index=key_value_pairs.index), parsed_arrays


def infer_county_for_points(
    points: gpd.GeoDataFrame, counties: gpd.GeoDataFrame
) -> pd.Series:
    join = gpd.sjoin(
        points[["geometry"]],
        counties[["county", "geometry"]],
        how="left",
        predicate="within",
    )
    counts = join.groupby(level=0)["county"].count().reindex(points.index, fill_value=0)

    bad_counts = counts != 1
    if bad_counts.any():
        bad_index = bad_counts.idxmax()
        point = points.loc[bad_index, "geometry"]
        intersects = counties[counties.intersects(point)]["county"].tolist()
        touches = counties[counties.touches(point)]["county"].tolist()
        fail(
            "point does not resolve to exactly one county",
            row_index=int(bad_index),
            point_wkt=point.wkt,
            within_count=int(counts.loc[bad_index]),
            intersecting_counties=intersects,
            touching_counties=touches,
        )

    return join.groupby(level=0)["county"].first().reindex(points.index)


def parse_selected_district(row_dict: dict, actual_county: str) -> dict:
    parsed_array = row_dict["parsed_result"]
    if len(parsed_array) == 0:
        fail("result is a valid JSON array but it is empty", row=row_dict)

    validated = []
    for object_index, obj in enumerate(parsed_array):
        if not isinstance(obj, dict):
            fail(
                "JSON array entry is not an object",
                row=row_dict,
                object_index=object_index,
                object_value=obj,
            )

        if str(obj.get("zip_code", "")) != row_dict["zip"]:
            fail(
                "zip_code in result does not match zip column",
                row=row_dict,
                object_index=object_index,
                zip_code=obj.get("zip_code"),
            )

        expected_prefix = f"{row_dict['num']} {row_dict['street']}"
        full_address = obj.get("full_address")
        if not isinstance(full_address, str) or not address_prefix_matches(
            expected_prefix, full_address
        ):
            return {
                "status": "address_mismatch",
                "object_index": object_index,
                "full_address": full_address,
                "expected_prefix": normalize_address_text(expected_prefix),
                "expected_tokens": normalize_address_tokens(expected_prefix),
                "full_address_tokens": normalize_address_tokens(full_address)
                if isinstance(full_address, str)
                else None,
            }

        districts = obj.get("districts")
        if not isinstance(districts, dict):
            fail(
                "result object does not contain a districts object",
                row=row_dict,
                object_index=object_index,
                object_value=obj,
            )

        for field in ["County", "Legislative", "Precinct"]:
            if field == "Legislative" and field not in districts and "Precinct" in districts:
                precinct_match = PRECINCT_RE.fullmatch(str(districts["Precinct"]))
                if precinct_match is None:
                    return {
                        "status": "unknown_precinct",
                        "object_index": object_index,
                        "precinct": districts.get("Precinct"),
                        "reason": "cannot_infer_legislative_from_precinct",
                    }
                if precinct_match.group(2) == "9999":
                    return {
                        "status": "unknown_precinct",
                        "object_index": object_index,
                        "precinct": districts.get("Precinct"),
                        "reason": "precinct_parenthesized_9999",
                    }
                inferred_district = int(precinct_match.group(1)[2:4])
                districts["Legislative"] = f"District {inferred_district:02d}"
            if field not in districts:
                fail(
                    "result object is missing a required districts field",
                    row=row_dict,
                    object_index=object_index,
                    missing_field=field,
                    districts=districts,
                )

        validated.append(obj)

    if len(validated) == 1:
        selected = validated[0]
    else:
        matching = [
            obj
            for obj in validated
            if obj["districts"]["County"] == actual_county
        ]
        if len(matching) == 0:
            return {
                "status": "no_county_match",
                "actual_county": actual_county,
                "county_values": [obj["districts"]["County"] for obj in validated],
            }
        if len(matching) > 1:
            return {
                "status": "ambiguous_county_match",
                "actual_county": actual_county,
                "county_values": [obj["districts"]["County"] for obj in validated],
            }
        selected = matching[0]

    legislative = selected["districts"]["Legislative"]
    legislative_match = LEGISLATIVE_RE.fullmatch(legislative)
    if legislative_match is None:
        fail(
            "Legislative field does not match expected format",
            row=row_dict,
            legislative=legislative,
        )

    district_digits = legislative_match.group(1)
    district_suffix = legislative_match.group(2)
    if district_suffix not in {"", "a", "A", "b", "B"}:
        fail(
            "Legislative suffix is not empty, A, or B",
            row=row_dict,
            legislative=legislative,
        )

    district_int = int(district_digits)
    district = str(district_int)
    if district_suffix:
        district += district_suffix.upper()

    precinct_value = selected["districts"]["Precinct"]
    precinct_match = PRECINCT_RE.fullmatch(precinct_value)
    if precinct_match is None:
        return {
            "status": "unknown_precinct",
            "precinct": precinct_value,
            "reason": "malformed_precinct",
        }

    precinct_digits = precinct_match.group(1)
    parenthesized = precinct_match.group(2)
    if parenthesized == "9999":
        return {
            "status": "unknown_precinct",
            "precinct": precinct_value,
            "reason": "precinct_parenthesized_9999",
        }
    if precinct_digits[2:6] != parenthesized:
        fail(
            "Precinct parentheses do not match digits 3-6 of the precinct number",
            row=row_dict,
            precinct=precinct_value,
            precinct_digits=precinct_digits,
            parenthesized=parenthesized,
        )

    if precinct_digits[2:4] != f"{district_int:02d}":
        fail(
            "Precinct digits 3-4 do not match Legislative district",
            row=row_dict,
            precinct=precinct_value,
            district=legislative,
        )

    return {
        "status": "selected",
        "county": selected["districts"]["County"],
        "district": district,
        "district_int": district_int,
        "precinct": precinct_digits,
        "county_int": int(precinct_digits[:2]),
        "precinct_int": int(precinct_digits[4:6]),
    }


def build_wheretovote(
    key_value_pairs: pd.DataFrame,
    addresses: gpd.GeoDataFrame,
    address_index: pd.Series,
    counties: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    valid_mask, parsed_arrays = parse_result_arrays(key_value_pairs)

    addresses_for_rows = addresses.iloc[address_index.to_numpy()].copy()
    addresses_for_rows.index = key_value_pairs.index

    valid_df = key_value_pairs.loc[valid_mask].copy()
    valid_df["parsed_result"] = [parsed_arrays[i] for i in valid_df.index]

    invalid_df = key_value_pairs.loc[~valid_mask].copy()

    valid_gdf = gpd.GeoDataFrame(
        valid_df,
        geometry=addresses_for_rows.loc[valid_df.index, "geometry"],
        crs=addresses.crs,
    ).to_crs(counties.crs)
    invalid_gdf = gpd.GeoDataFrame(
        invalid_df[["num", "zip", "street", "result"]].assign(
            reason="invalid_json_array",
            debug="",
        ),
        geometry=addresses_for_rows.loc[invalid_df.index, "geometry"],
        crs=addresses.crs,
    ).to_crs(counties.crs)

    actual_counties = infer_county_for_points(valid_gdf, counties)

    wheretovote_rows = []
    extra_missing_rows = []
    row_iterator = tqdm(
        valid_gdf.itertuples(index=True),
        total=len(valid_gdf),
        desc="Build wheretovote",
    )
    for row in row_iterator:
        row_index = row.Index
        row_dict = {
            "index": row.index,
            "num": row.num,
            "zip": row.zip,
            "street": row.street,
            "result": row.result,
            "parsed_result": row.parsed_result,
        }
        selected = parse_selected_district(row_dict, actual_counties.loc[row_index])
        if selected["status"] == "address_mismatch":
            extra_missing_rows.append(
                {
                    "num": row.num,
                    "zip": row.zip,
                    "street": row.street,
                    "result": row.result,
                    "reason": "address_mismatch",
                    "debug": safe_json(
                        {
                            "object_index": selected["object_index"],
                            "full_address": selected["full_address"],
                            "expected_prefix": selected["expected_prefix"],
                            "expected_tokens": selected["expected_tokens"],
                            "full_address_tokens": selected["full_address_tokens"],
                        }
                    ),
                    "geometry": row.geometry,
                }
            )
            continue
        if selected["status"] == "unknown_precinct":
            extra_missing_rows.append(
                {
                    "num": row.num,
                    "zip": row.zip,
                    "street": row.street,
                    "result": row.result,
                    "reason": "unknown_precinct",
                    "debug": safe_json(
                        {
                            "reason": selected["reason"],
                            "object_index": selected.get("object_index"),
                            "precinct": selected["precinct"],
                        }
                    ),
                    "geometry": row.geometry,
                }
            )
            continue
        if selected["status"] == "no_county_match":
            extra_missing_rows.append(
                {
                    "num": row.num,
                    "zip": row.zip,
                    "street": row.street,
                    "result": row.result,
                    "reason": "no_county_match",
                    "debug": safe_json(
                        {
                            "actual_county": selected["actual_county"],
                            "county_values": selected["county_values"],
                        }
                    ),
                    "geometry": row.geometry,
                }
            )
            continue
        if selected["status"] == "ambiguous_county_match":
            extra_missing_rows.append(
                {
                    "num": row.num,
                    "zip": row.zip,
                    "street": row.street,
                    "result": row.result,
                    "reason": "ambiguous_county_match",
                    "debug": safe_json(
                        {
                            "actual_county": selected["actual_county"],
                            "county_values": selected["county_values"],
                        }
                    ),
                    "geometry": row.geometry,
                }
            )
            continue
        wheretovote_rows.append(
            {
                "index": int(row.index),
                "num": row.num,
                "zip": row.zip,
                "street": row.street,
                "county": selected["county"],
                "district": selected["district"],
                "district_int": selected["district_int"],
                "precinct": selected["precinct"],
                "county_int": selected["county_int"],
                "precinct_int": selected["precinct_int"],
                "geometry": row.geometry,
            }
        )

    wheretovote = gpd.GeoDataFrame(wheretovote_rows, crs=valid_gdf.crs)
    if extra_missing_rows:
        extra_missing_gdf = gpd.GeoDataFrame(extra_missing_rows, crs=valid_gdf.crs)
        missing = pd.concat([invalid_gdf, extra_missing_gdf], ignore_index=True)
        missing = gpd.GeoDataFrame(missing, geometry="geometry", crs=valid_gdf.crs)
    else:
        missing = invalid_gdf
    return wheretovote, missing


def build_polling_fields(wheretovote: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    polling = pq.read_table(POLLING_PLACES_PATH).to_pandas()[POLLING_FIELDS].copy()
    polling["county_key"] = polling["county_number"].astype(str).str.zfill(2)
    polling["district_key"] = polling["legislative_district"].astype(str).str.zfill(2)
    polling["precinct_key"] = polling["precinct_number"].astype(str).str.zfill(2)

    wheretovote = wheretovote.copy()
    impute_mask = wheretovote["precinct"] == "083204"
    wheretovote.loc[impute_mask, "precinct"] = "083205"
    wheretovote.loc[impute_mask, "precinct_int"] = 5
    impute_mask = wheretovote["precinct"] == "320902"
    wheretovote.loc[impute_mask, "precinct"] = "320901"
    wheretovote.loc[impute_mask, "precinct_int"] = 1
    wheretovote["county_key"] = wheretovote["county_int"].astype(str).str.zfill(2)
    wheretovote["district_key"] = wheretovote["district_int"].astype(str).str.zfill(2)
    wheretovote["precinct_key"] = wheretovote["precinct_int"].astype(str).str.zfill(2)

    polling_by_key = {}
    for key, group in polling.groupby(["county_key", "district_key", "precinct_key"], sort=False):
        unique_records = (
            group[
                [
                    "county",
                    "polling_location",
                    "address",
                    "city",
                    "zip_code",
                    "polling_hours",
                    "county_auditor_phone",
                ]
            ]
            .drop_duplicates()
            .copy()
        )
        polling_counties = sorted(unique_records["county"].dropna().unique().tolist())
        unique_records["sort_key"] = unique_records.apply(
            lambda row: ", ".join(
                [row["polling_location"], row["address"], row["city"], row["zip_code"]]
            ),
            axis=1,
        )
        unique_records = unique_records.sort_values("sort_key")

        polling_objects = [
            {
                "location": row["polling_location"],
                "address": row["address"],
                "city": row["city"],
                "zip": row["zip_code"],
                "hours": row["polling_hours"],
                "phone": row["county_auditor_phone"],
            }
            for _, row in unique_records.iterrows()
        ]
        polling_min_strings = sorted(unique_records["sort_key"].drop_duplicates().tolist())
        polling_json = json.dumps(polling_objects, ensure_ascii=False, separators=(",", ":"))
        polling_min_json = json.dumps(
            polling_min_strings,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        polling_by_key[key] = {
            "polling": polling_json,
            "polling_min": polling_min_json,
            "polling_color": stable_color(polling_min_json),
            "polling_counties": polling_counties,
        }

    key_tuples = list(
        zip(
            wheretovote["county_key"],
            wheretovote["district_key"],
            wheretovote["precinct_key"],
        )
    )
    missing_keys = [key for key in key_tuples if key not in polling_by_key]
    if missing_keys:
        missing_key = missing_keys[0]
        row = wheretovote.loc[
            (wheretovote["county_key"] == missing_key[0])
            & (wheretovote["district_key"] == missing_key[1])
            & (wheretovote["precinct_key"] == missing_key[2])
        ].iloc[0]
        fail(
            "no polling-places match for county/district/precinct key",
            wheretovote_row=row.drop(labels=["geometry"]).to_dict(),
        )

    for key in set(key_tuples):
        info = polling_by_key[key]
        expected_counties = wheretovote.loc[
            (wheretovote["county_key"] == key[0])
            & (wheretovote["district_key"] == key[1])
            & (wheretovote["precinct_key"] == key[2]),
            "county",
        ].unique()
        expected_county = expected_counties[0]
        if any(county != expected_county for county in info["polling_counties"]):
            fail(
                "polling-places county does not match wheretovote county",
                county_key=key[0],
                district_key=key[1],
                precinct_key=key[2],
                expected_county=expected_county,
                polling_counties=info["polling_counties"],
            )

    wheretovote["polling"] = [polling_by_key[key]["polling"] for key in key_tuples]
    wheretovote["polling_min"] = [polling_by_key[key]["polling_min"] for key in key_tuples]
    wheretovote["polling_color"] = [
        polling_by_key[key]["polling_color"] for key in key_tuples
    ]
    return wheretovote.drop(columns=["county_key", "district_key", "precinct_key"])


def dissolve_with_attributes(gdf: gpd.GeoDataFrame, group_cols: list[str]) -> gpd.GeoDataFrame:
    dissolved = gdf.dissolve(by=group_cols)
    dissolved = dissolved.reset_index()
    return gpd.GeoDataFrame(dissolved, geometry="geometry", crs=gdf.crs)


def build_voronoi_areas(
    wheretovote: gpd.GeoDataFrame, counties: gpd.GeoDataFrame, districts: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    intersections = gpd.overlay(
        counties[["county", "county_fp", "geometry"]],
        districts[["district", "district_int", "geometry"]],
        how="intersection",
    )
    intersections = intersections[~intersections.geometry.is_empty].copy()

    intersections_proj = intersections.to_crs(VORONOI_CRS)
    wheretovote_proj = wheretovote.to_crs(VORONOI_CRS)

    polling_areas = []
    area_iterator = tqdm(
        intersections_proj.itertuples(index=False),
        total=len(intersections_proj),
        desc="Build Voronoi areas",
    )
    for area in area_iterator:
        in_area = wheretovote_proj.within(area.geometry)
        points = wheretovote_proj.loc[in_area].copy()
        if len(points) == 0:
            continue

        unique_geometries = []
        geometry_to_cell = {}
        for geometry in points.geometry:
            key = geometry.wkb_hex
            if key not in geometry_to_cell:
                unique_geometries.append(geometry)
                geometry_to_cell[key] = None

        if len(unique_geometries) == 1:
            cells = [area.geometry]
        else:
            multi_point = MultiPoint(unique_geometries)
            voronoi = voronoi_polygons(
                multi_point,
                extend_to=area.geometry,
                ordered=True,
            )
            cells = list(voronoi.geoms)
            if len(cells) != len(unique_geometries):
                fail(
                    "Voronoi polygon count does not match unique point count",
                    county=area["county"],
                    district=area["district"],
                    unique_point_count=len(unique_geometries),
                    cell_count=len(cells),
                )

        for geometry, cell in zip(unique_geometries, cells):
            geometry_to_cell[geometry.wkb_hex] = cell.intersection(area.geometry)

        original_voronoi = points.copy()
        original_voronoi["geometry"] = original_voronoi.geometry.map(
            lambda geometry: geometry_to_cell[geometry.wkb_hex]
        )
        original_voronoi = original_voronoi[~original_voronoi.geometry.is_empty].copy()

        polling_group_cols = [
            "county",
            "county_int",
            "district",
            "district_int",
            "polling_min",
            "polling",
            "polling_color",
        ]

        polling_areas.append(dissolve_with_attributes(original_voronoi, polling_group_cols))

    polling_gdf = (
        gpd.GeoDataFrame(
            pd.concat(polling_areas, ignore_index=True),
            geometry="geometry",
            crs=intersections_proj.crs,
        ).to_crs(counties.crs)
        if polling_areas
        else gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=counties.crs)
    )
    return polling_gdf


def remove_small_polling_area_components(
    polling_areas: gpd.GeoDataFrame,
    wheretovote_points: gpd.GeoDataFrame,
    min_addresses: int,
) -> gpd.GeoDataFrame:
    if min_addresses <= 0 or len(polling_areas) == 0:
        return polling_areas

    components = polling_areas.explode(index_parts=False).reset_index(drop=True)
    if len(components) == 0:
        return polling_areas.iloc[0:0].copy()

    components = components.reset_index(names="component_id")
    join = gpd.sjoin(
        components[["component_id", "geometry"]],
        wheretovote_points[["geometry"]],
        how="left",
        predicate="contains",
    )
    counts = (
        join.groupby("component_id")["index_right"]
        .count()
        .reindex(components["component_id"], fill_value=0)
    )
    kept = components.loc[counts >= min_addresses].drop(columns=["component_id"])
    if len(kept) == 0:
        return polling_areas.iloc[0:0].copy()

    group_cols = [column for column in kept.columns if column != "geometry"]
    return dissolve_with_attributes(kept, group_cols)


def write_gpkg(gdf: gpd.GeoDataFrame, path: Path) -> None:
    if path.exists():
        path.unlink()
    gdf.to_file(path, driver="GPKG")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--min-addresses",
        type=int,
        default=DEFAULT_MIN_ADDRESSES,
        help="Drop simply connected polling-area polygons containing fewer than this many wheretovote points.",
    )
    args = parser.parse_args()
    if args.min_addresses < 0:
        parser.error("--min-addresses must be non-negative")
    return args


def main() -> int:
    args = parse_args()
    key_value_pairs = read_key_value_pairs()
    addresses = read_addresses()
    counties = gpd.read_file(COUNTIES_PATH)
    districts = gpd.read_file(DISTRICTS_PATH)

    address_index = validate_index_alignment(key_value_pairs, addresses)
    wheretovote, missing = build_wheretovote(
        key_value_pairs,
        addresses,
        address_index,
        counties,
    )
    wheretovote = build_polling_fields(wheretovote)

    write_gpkg(wheretovote, WHERETOVOTE_POINTS_PATH)
    write_gpkg(missing, MISSING_POINTS_PATH)

    polling_areas = build_voronoi_areas(wheretovote, counties, districts)
    polling_areas = remove_small_polling_area_components(
        polling_areas,
        wheretovote,
        args.min_addresses,
    )
    write_gpkg(polling_areas, POLLING_AREAS_PATH)
    if LEGACY_PRECINCT_AREAS_PATH.exists():
        LEGACY_PRECINCT_AREAS_PATH.unlink()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
