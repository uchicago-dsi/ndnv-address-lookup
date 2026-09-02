#!/usr/bin/env python3

import argparse
import csv
import html
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent / "public" / "polling-places.parquet"
)
OUTPUT_CSV_PATH = (
    Path(__file__).resolve().parent.parent / "public" / "polling-places-nodups.csv"
)
DROPBOXES_CSV_PATH = (
    Path(__file__).resolve().parent.parent / "public" / "dropboxes.csv"
)
EARLY_VOTING_CSV_PATH = (
    Path(__file__).resolve().parent.parent / "public" / "early-voting.csv"
)
SUPPLEMENT_PATH = Path(__file__).resolve().parent / "precincts-supplement.json"

FIELD_NAMES = {
    "County": "county",
    "County Number": "county_number",
    "Legislative District": "legislative_district",
    "Precinct Number": "precinct_number",
    "Polling Location": "polling_location",
    "Address": "address",
    "City": "city",
    "State": "state",
    "Zip Code": "zip_code",
    "Polling Hours": "polling_hours",
    "County Auditor Phone": "county_auditor_phone",
}

SLIM_FIELD_NAMES = [
    "polling_location",
    "address",
    "city",
    "county",
    "zip_code",
    "polling_hours",
    "county_auditor_phone",
]


def get_hidden_input_value(page_html: str, name: str) -> str:
    pattern = re.compile(
        rf'<input[^>]*name="{re.escape(name)}"[^>]*value="([\s\S]*?)"[^>]*>'
    )
    match = pattern.search(page_html)
    if match is None:
        raise RuntimeError(f"Could not find hidden input {name}")
    return html.unescape(match.group(1))


def fetch_text(request: urllib.request.Request) -> str:
    with urllib.request.urlopen(request) as response:
        return response.read().decode("utf-8")


def fetch_bytes(request: urllib.request.Request) -> tuple[bytes, str]:
    with urllib.request.urlopen(request) as response:
        content_type = response.headers.get("Content-Type", "")
        return response.read(), content_type


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    # 346 was the June 9, 2026 primary; 348 is the November 3, 2026 general election.
    # The current mapping is listed at
    # https://www.sos.nd.gov/elections/voter/elections-currentpast
    # Re-derive it there rather than assuming this default is still right.
    parser.add_argument("eid", nargs="?", default="348", help="Election ID")
    return parser.parse_args()


def build_source_url(eid: str) -> str:
    return f"https://vip.sos.nd.gov/Precincts.aspx?eid={eid}"


def export_csv_bytes(source_url: str, tab_index: int) -> bytes:
    page_request = urllib.request.Request(
        source_url,
        headers={"User-Agent": "python-urllib"},
    )
    page_html = fetch_text(page_request)

    form_data = {
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$btnExport",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": get_hidden_input_value(page_html, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": get_hidden_input_value(
            page_html, "__VIEWSTATEGENERATOR"
        ),
        "__EVENTVALIDATION": get_hidden_input_value(page_html, "__EVENTVALIDATION"),
        "ctl00$ContentPlaceHolder1$btnExport": "Export to Excel",
        # These Telerik client-state fields reproduce selecting the
        # requested tab before exporting.
        "ctl00_ContentPlaceHolder1_rtsPrecincts_ClientState": (
            f'{{"selectedIndexes":["{tab_index}"]}}'
        ),
        "ctl00_ContentPlaceHolder1_rmpPrecincts_ClientState": (
            f'{{"selectedIndex":{tab_index}}}'
        ),
    }

    export_request = urllib.request.Request(
        source_url,
        data=urllib.parse.urlencode(form_data).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": source_url,
            "User-Agent": "python-urllib",
        },
        method="POST",
    )
    csv_bytes, content_type = fetch_bytes(export_request)

    if "text/csv" not in content_type:
        raise RuntimeError(f"Unexpected export content type: {content_type}")

    return csv_bytes


def csv_bytes_to_table(
    csv_bytes: bytes, extra_rows: list[dict[str, str]] | None = None
) -> pa.Table:
    csv_text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))
    columns = {json_key: [] for json_key in FIELD_NAMES.values()}

    for row in reader:
        for csv_key, json_key in FIELD_NAMES.items():
            columns[json_key].append((row[csv_key] or "").strip())

    for row in extra_rows or []:
        for json_key in FIELD_NAMES.values():
            columns[json_key].append((row.get(json_key) or "").strip())

    return pa.table(
        {name: pa.array(values, type=pa.string()) for name, values in columns.items()}
    )


def load_supplement(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("counties", [])


def supplement_polling_rows(
    supplement: list[dict], present_counties: set[str]
) -> list[dict[str, str]]:
    """Rows for counties the SOS export omits but WhereToVote publishes.

    Skipped as soon as the export carries the county itself, so this cannot
    double-count once the SOS fixes the export. See scripts/precincts-supplement.json
    for why each county is listed.
    """
    rows: list[dict[str, str]] = []
    for entry in supplement:
        county = entry["county"]
        if county in present_counties:
            print(
                f"SKIP supplement: {county} is now in the SOS export "
                f"({len(entry['precinct_numbers']) * len(entry['polling_locations'])} "
                f"rows not added). Re-verify and delete it from "
                f"{SUPPLEMENT_PATH.name}.",
                file=sys.stderr,
            )
            continue
        print(
            f"SUPPLEMENT: adding {county} from WhereToVote "
            f"(absent from the SOS export; verified {entry['verified']})",
            file=sys.stderr,
        )
        for precinct in entry["precinct_numbers"]:
            for location in entry["polling_locations"]:
                rows.append(
                    {
                        "county": county,
                        "county_number": entry["county_number"],
                        "legislative_district": entry["legislative_district"],
                        "precinct_number": precinct,
                        "polling_location": location["polling_location"],
                        "address": location["address"],
                        "city": location["city"],
                        "state": "ND",
                        "zip_code": location["zip_code"],
                        "polling_hours": entry["polling_hours"],
                        "county_auditor_phone": entry["county_auditor_phone"],
                    }
                )
    return rows


def supplement_dropbox_rows(
    supplement: list[dict], present_counties: set[str]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in supplement:
        if entry["county"] in present_counties:
            continue
        for dropbox in entry.get("dropboxes", []):
            rows.append(
                {
                    "county": entry["county"],
                    "county_fp": county_number_to_county_fp(entry["county_number"]),
                    "polling_location": dropbox["polling_location"],
                    "address": dropbox["address"],
                    "city": dropbox["city"],
                    "state": "ND",
                    "zip_code": dropbox["zip_code"],
                    "polling_hours": dropbox["polling_hours"],
                    "county_auditor_phone": dropbox["county_auditor_phone"],
                }
            )
    return rows


def snake_case_column_name(name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", name.strip())
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized.lower()


def county_number_to_county_fp(value: str) -> str:
    county_number = int(value.strip())
    return str(2 * county_number - 1)


def write_csv_with_snake_case_headers(
    csv_bytes: bytes,
    output_path: Path,
    extra_rows: list[dict[str, str]] | None = None,
) -> None:
    csv_text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise RuntimeError("Exported CSV is missing headers")

    fieldnames = []
    for name in reader.fieldnames:
        snake_name = snake_case_column_name(name)
        if snake_name == "county_number":
            snake_name = "county_fp"
        fieldnames.append(snake_name)

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            output_row = {}
            for name, value in row.items():
                if name is None:
                    continue
                snake_name = snake_case_column_name(name)
                cleaned_value = (value or "").strip()
                if snake_name == "county_number":
                    output_row["county_fp"] = county_number_to_county_fp(cleaned_value)
                else:
                    output_row[snake_name] = cleaned_value
            writer.writerow(output_row)

        for row in extra_rows or []:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def write_slim_deduplicated_csv(table: pa.Table, output_path: Path) -> None:
    rows = zip(*(table.column(name).to_pylist() for name in SLIM_FIELD_NAMES), strict=True)
    seen: set[tuple[str, ...]] = set()

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=SLIM_FIELD_NAMES)
        writer.writeheader()

        for row_values in rows:
            if row_values in seen:
                continue
            seen.add(row_values)
            writer.writerow(dict(zip(SLIM_FIELD_NAMES, row_values, strict=True)))


EARLY_VOTING_FIELD_NAMES = {
    "County": "county",
    "Early Voting Location": "early_voting_location",
    "Address": "address",
    "City": "city",
    "State": "state",
    "ZipCode": "zip_code",
    "Early Voting Date and Times": "early_voting_times",
    "Comments": "comments",
}

EARLY_VOTING_OUTPUT_FIELD_NAMES = [
    "county",
    "county_fp",
    "early_voting_location",
    "address",
    "city",
    "state",
    "zip_code",
    "early_voting_times",
    "comments",
]


def county_name_to_number(*csv_bytes_with_county_number: bytes) -> dict[str, str]:
    """Map county name -> the SOS "County Number", read from any tab that has it.

    The "Early Voting Available Counties" tab (index 4) is the only one that
    names counties without numbering them, so the number has to be borrowed
    from a tab that does. Several tabs are consulted because an individual tab
    can be missing a county entirely when the county has not reported yet.
    """
    mapping: dict[str, str] = {}
    for csv_bytes in csv_bytes_with_county_number:
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
        for row in reader:
            county = (row.get("County") or "").strip()
            number = (row.get("County Number") or "").strip()
            if county and number:
                mapping.setdefault(county, number)
    return mapping


def write_early_voting_csv(
    csv_bytes: bytes, county_numbers: dict[str, str], output_path: Path
) -> None:
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
    if reader.fieldnames is None:
        raise RuntimeError("Exported early-voting CSV is missing headers")

    missing_headers = set(EARLY_VOTING_FIELD_NAMES) - {
        name.strip() for name in reader.fieldnames
    }
    if missing_headers:
        raise RuntimeError(
            f"Early-voting export is missing columns: {sorted(missing_headers)}"
        )

    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file, fieldnames=EARLY_VOTING_OUTPUT_FIELD_NAMES
        )
        writer.writeheader()

        for row in reader:
            county = (row["County"] or "").strip()
            if county not in county_numbers:
                # Refuse to guess: a wrong county_fp would show these locations
                # to the wrong voters.
                raise RuntimeError(
                    f"No County Number found for early-voting county {county!r}"
                )
            output_row = {
                json_key: (row[csv_key] or "").strip()
                for csv_key, json_key in EARLY_VOTING_FIELD_NAMES.items()
            }
            output_row["county_fp"] = county_number_to_county_fp(
                county_numbers[county]
            )
            writer.writerow(output_row)


def main() -> int:
    args = parse_args()
    source_url = build_source_url(args.eid)
    polling_places_csv_bytes = export_csv_bytes(source_url, tab_index=5)
    dropboxes_csv_bytes = export_csv_bytes(source_url, tab_index=2)
    county_polling_csv_bytes = export_csv_bytes(source_url, tab_index=1)
    early_voting_csv_bytes = export_csv_bytes(source_url, tab_index=4)

    exported_counties = {
        (row.get("County") or "").strip()
        for row in csv.DictReader(
            io.StringIO(polling_places_csv_bytes.decode("utf-8-sig"))
        )
    }
    supplement = load_supplement(SUPPLEMENT_PATH)
    table = csv_bytes_to_table(
        polling_places_csv_bytes,
        supplement_polling_rows(supplement, exported_counties),
    )
    pq.write_table(
        table,
        OUTPUT_PATH,
        compression="snappy",
        use_dictionary=list(table.schema.names),
    )
    write_slim_deduplicated_csv(table, OUTPUT_CSV_PATH)
    write_csv_with_snake_case_headers(
        dropboxes_csv_bytes,
        DROPBOXES_CSV_PATH,
        supplement_dropbox_rows(supplement, exported_counties),
    )
    write_early_voting_csv(
        early_voting_csv_bytes,
        county_name_to_number(
            polling_places_csv_bytes,
            dropboxes_csv_bytes,
            county_polling_csv_bytes,
        ),
        EARLY_VOTING_CSV_PATH,
    )
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Wrote {OUTPUT_CSV_PATH}")
    print(f"Wrote {DROPBOXES_CSV_PATH}")
    print(f"Wrote {EARLY_VOTING_CSV_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
