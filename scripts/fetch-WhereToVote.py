#!/usr/bin/env python3

import argparse
from pathlib import Path
import random
import re
from urllib.parse import urljoin

import pyarrow.parquet as pq
import requests
from bs4 import BeautifulSoup


PARQUET_PATH = (
    Path(__file__).resolve().parent.parent / "public" / "911-addresses.parquet"
)
COLUMNS = ["num", "street", "zip", "lon", "lat"]
WHERE_TO_VOTE_URL = "https://vip.sos.nd.gov/WhereToVote.aspx"
HOUSE_INPUT_ID = "ctl00_ContentPlaceHolder1_txtHouseNumber"
ZIP_INPUT_ID = "ctl00_ContentPlaceHolder1_txtZip"
ADDRESS_SEARCH_BUTTON_ID = "ctl00_ContentPlaceHolder1_btnSearch"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start", type=int, default=0, help="Index of first entry to print"
    )
    parser.add_argument("--size", type=int, help="Number of entries to print")
    parser.add_argument(
        "--randomize", action="store_true", help="Process selected rows in random order"
    )
    parser.add_argument(
        "--previous",
        type=Path,
        help="Text file of prior output lines; rows with those global indices are skipped",
    )
    return parser.parse_args()


def parse_form(
    html: str,
) -> tuple[str, dict[str, str], str, str, tuple[str, str] | None]:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if form is None:
        raise RuntimeError("Could not find form on the page")

    house_input = form.find(id=HOUSE_INPUT_ID)
    zip_input = form.find(id=ZIP_INPUT_ID)
    if house_input is None or zip_input is None:
        raise RuntimeError("Could not find house number or zip inputs on the page")

    house_name = house_input.get("name")
    zip_name = zip_input.get("name")
    if not house_name or not zip_name:
        raise RuntimeError(
            "Could not resolve form field names for house number and zip"
        )

    submit_button = form.find(id=ADDRESS_SEARCH_BUTTON_ID)
    submit_name = submit_button.get("name") if submit_button is not None else None
    submit_value = submit_button.get("value", "") if submit_button is not None else ""

    payload: dict[str, str] = {}
    for hidden_input in form.find_all("input", attrs={"type": "hidden"}):
        name = hidden_input.get("name")
        if name:
            payload[name] = hidden_input.get("value", "")

    button = (submit_name, submit_value) if submit_name else None
    return form.get("action", ""), payload, house_name, zip_name, button


def to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    return str(value)


def normalize_address(text: str) -> str:
    normalized = re.sub(r"[^0-9a-z]+", " ", text.casefold())
    return " ".join(normalized.split())


def find_part_for_address(
    html: str, house_number: object, street: object
) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    target = normalize_address(f"{to_text(house_number)} {to_text(street)}")
    rows = soup.select("tr.rgRow[id*='rgAddresses'], tr.rgAltRow[id*='rgAddresses']")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        part = cells[0].get_text(" ", strip=True)
        row_address = cells[1].get_text(" ", strip=True)
        if normalize_address(row_address) == target:
            return part
    return None


def fetch_where_to_vote_html(
    session: requests.Session, house_number: object, zip_code: object
) -> str:
    get_response = session.get(WHERE_TO_VOTE_URL, timeout=30)
    get_response.raise_for_status()

    form_action, payload, house_name, zip_name, submit_button = parse_form(
        get_response.text
    )
    payload[house_name] = to_text(house_number)
    payload[zip_name] = to_text(zip_code)
    if submit_button is not None:
        payload[submit_button[0]] = submit_button[1]

    post_url = (
        urljoin(WHERE_TO_VOTE_URL, form_action) if form_action else WHERE_TO_VOTE_URL
    )
    post_response = session.post(post_url, data=payload, timeout=30)
    post_response.raise_for_status()
    return post_response.text


def load_previous_indices(path: Path) -> set[int]:
    previous: set[int] = set()
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            stripped = line.strip()
            if not stripped:
                continue
            first_token = stripped.split(maxsplit=1)[0]
            try:
                previous.add(int(first_token))
            except ValueError:
                continue
    return previous


def main() -> None:
    args = parse_args()
    if args.start < 0:
        raise ValueError("--start must be >= 0")

    parquet_file = pq.ParquetFile(PARQUET_PATH)
    total_rows = parquet_file.metadata.num_rows
    start = args.start

    if start > total_rows:
        raise ValueError(f"--start ({start}) is larger than row count ({total_rows})")

    size = args.size if args.size is not None else total_rows - start
    if size < 0:
        raise ValueError("--size must be >= 0")

    end = start + size
    if end > total_rows:
        raise ValueError(f"--start + --size ({end}) exceeds row count ({total_rows})")

    previous_indices: set[int] = set()
    if args.previous is not None:
        previous_indices = load_previous_indices(args.previous)

    pending_rows: list[tuple[int, object, object, object]] = []
    with requests.Session() as session:
        row_offset = 0
        for row_group_index in range(parquet_file.metadata.num_row_groups):
            row_group = parquet_file.metadata.row_group(row_group_index)
            row_group_rows = row_group.num_rows
            row_group_start = row_offset
            row_group_end = row_offset + row_group_rows
            row_offset = row_group_end

            overlap_start = max(start, row_group_start)
            overlap_end = min(end, row_group_end)
            overlap_size = overlap_end - overlap_start
            if overlap_size <= 0:
                if row_group_start >= end:
                    break
                continue

            table = parquet_file.read_row_group(row_group_index, columns=COLUMNS)
            local_start = overlap_start - row_group_start
            selected = table.slice(local_start, overlap_size)

            num_col = selected.column("num").to_pylist()
            street_col = selected.column("street").to_pylist()
            zip_col = selected.column("zip").to_pylist()

            for local_index, (num, street, zipcode) in enumerate(
                zip(num_col, street_col, zip_col)
            ):
                global_index = overlap_start + local_index
                pending_rows.append((global_index, num, street, zipcode))

        if args.randomize:
            random.shuffle(pending_rows)

        for global_index, num, street, zipcode in pending_rows:
            if global_index in previous_indices:
                continue
            html = fetch_where_to_vote_html(session, num, zipcode)
            part = find_part_for_address(html, num, street)
            print(
                f"{global_index} {part if part is not None else 'NO_MATCH'}", flush=True
            )


if __name__ == "__main__":
    main()
