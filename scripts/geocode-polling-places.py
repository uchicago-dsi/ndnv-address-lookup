#!/usr/bin/env python3

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


DEFAULT_INPUT_PATH = (
    Path(__file__).resolve().parent.parent / "public" / "polling-places-nodups.csv"
)
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent / "public" / "polling-places-locations.json"
)

CENSUS_ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/address"
NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"

COORDINATE_PROVIDER_ORDER = ("census", "nominatim")
LABEL_PROVIDER_ORDER = ("nominatim", "census")
PROVIDER_MIN_DELAY_SECONDS = {
    "census": 0.0,
    "nominatim": 1.0,
}


@dataclass(frozen=True)
class GeocodeResult:
    provider: str
    longitude: float
    latitude: float
    label: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Input CSV of polling places",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSON mapping polling_location to [lon, lat]",
    )
    parser.add_argument(
        "--benchmark",
        default="Public_AR_Current",
        help="Census benchmark value",
    )
    parser.add_argument(
        "--user-agent",
        default="ndnv-address-lookup/1.0",
        help="HTTP User-Agent header",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Only process polling locations containing this substring",
    )
    return parser.parse_args()


def fetch_json(url: str, params: dict[str, str], user_agent: str) -> dict | list:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        full_url,
        headers={
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def load_rows(input_path: Path) -> list[dict[str, str]]:
    with input_path.open(newline="", encoding="utf-8") as input_file:
        rows = list(csv.DictReader(input_file))
    return [{key: (value or "").strip() for key, value in row.items()} for row in rows]


def load_existing_locations(output_path: Path) -> dict[str, list[float]]:
    if not output_path.exists():
        return {}

    data = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object in {output_path}")

    locations: dict[str, list[float]] = {}
    for key, value in data.items():
        if (
            not isinstance(key, str)
            or not isinstance(value, list)
            or len(value) != 2
            or not all(isinstance(item, (int, float)) for item in value)
        ):
            raise RuntimeError(f"Unexpected entry in {output_path}: {key!r}: {value!r}")
        locations[key] = [float(value[0]), float(value[1])]
    return locations


def write_locations(output_path: Path, locations: dict[str, list[float]]) -> None:
    output_path.write_text(
        json.dumps(locations, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_address(row: dict[str, str]) -> dict[str, str]:
    return {
        "street": row["address"],
        "city": row["city"],
        "state": "ND",
        "zip": row["zip_code"],
    }


def geocode_with_census(
    row: dict[str, str], benchmark: str, user_agent: str
) -> GeocodeResult:
    data = fetch_json(
        CENSUS_ENDPOINT,
        {
            **build_address(row),
            "benchmark": benchmark,
            "format": "json",
        },
        user_agent,
    )
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        raise RuntimeError(
            "No Census match for "
            f"{row['address']}, {row['city']}, ND {row['zip_code']}"
        )

    best = matches[0]
    coordinates = best["coordinates"]
    return GeocodeResult(
        provider="census",
        longitude=float(coordinates["x"]),
        latitude=float(coordinates["y"]),
        label=str(best["matchedAddress"]),
    )


def geocode_with_nominatim(row: dict[str, str], user_agent: str) -> GeocodeResult:
    data = fetch_json(
        NOMINATIM_ENDPOINT,
        {
            "street": row["address"],
            "city": row["city"],
            "county": row["county"],
            "state": "North Dakota",
            "country": "United States",
            "postalcode": row["zip_code"],
            "format": "jsonv2",
            "limit": "1",
            "addressdetails": "1",
        },
        user_agent,
    )
    if not data:
        raise RuntimeError(
            "No Nominatim match for "
            f"{row['address']}, {row['city']}, {row['county']}, ND {row['zip_code']}"
        )

    best = data[0]
    return GeocodeResult(
        provider="nominatim",
        longitude=float(best["lon"]),
        latitude=float(best["lat"]),
        label=str(best["display_name"]),
    )


class Geocoder:
    def __init__(self, benchmark: str, user_agent: str):
        self.benchmark = benchmark
        self.user_agent = user_agent
        self.last_request_at: dict[str, float] = {}

    def geocode(self, provider: str, row: dict[str, str]) -> GeocodeResult:
        self._sleep_if_needed(provider)

        if provider == "census":
            result = geocode_with_census(row, self.benchmark, self.user_agent)
        elif provider == "nominatim":
            result = geocode_with_nominatim(row, self.user_agent)
        else:
            raise AssertionError(f"Unsupported provider: {provider}")

        self.last_request_at[provider] = time.monotonic()
        return result

    def _sleep_if_needed(self, provider: str) -> None:
        min_delay = PROVIDER_MIN_DELAY_SECONDS[provider]
        if min_delay <= 0:
            return

        last_request_at = self.last_request_at.get(provider)
        if last_request_at is None:
            return

        elapsed = time.monotonic() - last_request_at
        remaining = min_delay - elapsed
        if remaining > 0:
            time.sleep(remaining)


def try_providers(
    row: dict[str, str],
    providers: tuple[str, ...],
    geocoder: Geocoder,
) -> tuple[GeocodeResult | None, list[str]]:
    errors: list[str] = []

    for provider in providers:
        try:
            return geocoder.geocode(provider, row), errors
        except Exception as error:
            errors.append(f"{provider}: {error}")

    return None, errors


def resolve_row(
    row: dict[str, str],
    geocoder: Geocoder,
) -> tuple[GeocodeResult | None, GeocodeResult | None, list[str]]:
    coordinate_result, coordinate_errors = try_providers(
        row,
        COORDINATE_PROVIDER_ORDER,
        geocoder,
    )
    if coordinate_result is None:
        return None, None, coordinate_errors

    label_result, label_errors = try_providers(
        row,
        LABEL_PROVIDER_ORDER,
        geocoder,
    )
    return coordinate_result, label_result, label_errors


def should_process(row: dict[str, str], only: str | None) -> bool:
    if only is None:
        return True
    return only.lower() in row["polling_location"].lower()


def main() -> int:
    args = parse_args()
    rows = load_rows(args.input)
    locations = load_existing_locations(args.output)
    geocoder = Geocoder(args.benchmark, args.user_agent)

    failures = 0

    for row in rows:
        polling_location = row["polling_location"]
        if not should_process(row, args.only):
            continue
        if polling_location in locations:
            print(f"SKIP\t{polling_location}", file=sys.stderr)
            continue

        coordinate_result, label_result, errors = resolve_row(row, geocoder)
        if coordinate_result is None:
            failures += 1
            print(f"FAIL\t{polling_location}", file=sys.stderr)
            for error in errors:
                print(f"  {error}", file=sys.stderr)
            continue

        if label_result is None:
            label = coordinate_result.label
            print(f"WARN\t{polling_location}", file=sys.stderr)
            for error in errors:
                print(f"  {error}", file=sys.stderr)
        else:
            label = label_result.label

        locations[polling_location] = [
            coordinate_result.longitude,
            coordinate_result.latitude,
        ]
        write_locations(args.output, locations)
        print(
            f"{polling_location}\t{label}\t"
            f"[coords={coordinate_result.provider}, label="
            f"{label_result.provider if label_result is not None else coordinate_result.provider}]"
        )

    print(f"Wrote {args.output}", file=sys.stderr)
    if failures > 0:
        print(f"{failures} polling place(s) could not be geocoded", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
