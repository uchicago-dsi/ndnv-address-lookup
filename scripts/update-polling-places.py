#!/usr/bin/env python3

import argparse
import csv
import html
import io
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
    parser.add_argument("eid", nargs="?", default="346", help="Election ID")
    return parser.parse_args()


def build_source_url(eid: str) -> str:
    return f"https://vip.sos.nd.gov/Precincts.aspx?eid={eid}"


def export_csv_bytes(source_url: str) -> bytes:
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
        # "Statewide Polling Places" tab before exporting.
        "ctl00_ContentPlaceHolder1_rtsPrecincts_ClientState": (
            '{"selectedIndexes":["5"]}'
        ),
        "ctl00_ContentPlaceHolder1_rmpPrecincts_ClientState": '{"selectedIndex":5}',
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


def csv_bytes_to_table(csv_bytes: bytes) -> pa.Table:
    csv_text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(csv_text))
    columns = {json_key: [] for json_key in FIELD_NAMES.values()}

    for row in reader:
        for csv_key, json_key in FIELD_NAMES.items():
            columns[json_key].append((row[csv_key] or "").strip())

    return pa.table(
        {name: pa.array(values, type=pa.string()) for name, values in columns.items()}
    )


def main() -> int:
    args = parse_args()
    source_url = build_source_url(args.eid)
    csv_bytes = export_csv_bytes(source_url)
    table = csv_bytes_to_table(csv_bytes)
    pq.write_table(
        table,
        OUTPUT_PATH,
        compression="snappy",
        use_dictionary=list(table.schema.names),
    )
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
