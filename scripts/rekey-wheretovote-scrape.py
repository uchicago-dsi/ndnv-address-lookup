#!/usr/bin/env python3
"""Re-key the WhereToVote scrape from row positions onto a rebuilt address file.

Why this exists
---------------
key-value-pairs.csv, wheretovote-points.gpkg, step2 and step3 all identify an
address by its *integer row position* in public/911-addresses.parquet. Rebuilding
that file from a newer GIS Hub export shifts every position, so the existing scrape
would be silently misaligned -- addresses would inherit other addresses' polling
places. (scripts/step2-analyze-wheretovote.py does catch this: its
validate_index_alignment() compares num/zip/street at each index and aborts.)

WhereToVote's answer depends only on (house number, ZIP, street), never on row
position, so the scrape can be re-keyed instead of re-run. That turns a multi-day
re-scrape of 431,238 addresses into a few minutes of local work.

Matching is done on a NORMALIZED street name, using the same abbreviation rules as
scripts/step0-fetch-WhereToVote-districts.py. This matters: the 2026-09 export
spells some values out ("Drive", "Northeast") and mixed-cases others where the
2025-04 export was uppercase and abbreviated. Raw string matching finds 96.83% of
addresses; normalized matching finds 98.52%, recovering ~6,040 addresses that would
otherwise have silently dropped from an official WhereToVote answer to a merely
inferred one.

The output keeps step2's expected columns and, critically, takes num/zip/street
from the NEW parquet so that validate_index_alignment() passes.
"""

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ADDRESSES = REPO_ROOT / "public" / "911-addresses.parquet"
DEFAULT_INPUT = (
    Path(
        "~/Box/dsi-core/11th-hour/ndnv-address-lookup/where-to-vote-2026"
        "/fetch-WhereToVote/key-value-pairs.csv"
    ).expanduser()
)

# Same spirit as step0's `replacements`, extended with the spellings the 2026
# export introduced. Only used for MATCHING; the emitted street is the parquet's.
STREET_WORD_REPLACEMENTS = {
    "street": "st",
    "road": "rd",
    "avenue": "ave",
    "boulevard": "blvd",
    "drive": "dr",
    "lane": "ln",
    "route": "rt",
    "court": "ct",
    "circle": "cir",
    "place": "pl",
    "terrace": "ter",
    "parkway": "pkwy",
    "highway": "hwy",
    "trail": "trl",
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "northeast": "ne",
    "northwest": "nw",
    "southeast": "se",
    "southwest": "sw",
}


def normalize_street(street: str) -> str:
    collapsed = re.sub(r"[^0-9a-z]+", " ", street.casefold())
    return " ".join(
        STREET_WORD_REPLACEMENTS.get(word, word) for word in collapsed.split()
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addresses", type=Path, default=DEFAULT_ADDRESSES)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Re-keyed key-value-pairs CSV (point step2 at this)",
    )
    return parser.parse_args()


def build_lookup(addresses_path: Path) -> tuple[dict, list]:
    table = pq.read_table(addresses_path, columns=["num", "street", "zip"])
    nums = table.column("num").to_pylist()
    streets = table.column("street").to_pylist()
    zips = table.column("zip").to_pylist()

    lookup = defaultdict(list)
    for position, (num, street, zip_code) in enumerate(zip(nums, streets, zips)):
        lookup[(str(num), zip_code, normalize_street(street))].append(position)
    print(
        f"{len(nums):,} addresses -> {len(lookup):,} distinct (num, zip, street) keys",
        file=sys.stderr,
    )
    return lookup, list(zip(nums, streets, zips))


def main() -> int:
    args = parse_args()
    lookup, rows = build_lookup(args.addresses)

    csv.field_size_limit(1 << 30)
    seen_positions: set[int] = set()
    records_read = 0
    records_matched = 0

    with args.input.open(newline="", encoding="utf-8") as input_file, args.output.open(
        "w", newline="", encoding="utf-8"
    ) as output_file:
        reader = csv.DictReader(input_file)
        missing = {"index", "num", "zip", "street", "result"} - set(
            reader.fieldnames or []
        )
        if missing:
            raise RuntimeError(f"{args.input} is missing columns: {sorted(missing)}")

        writer = csv.DictWriter(
            output_file, fieldnames=["index", "num", "zip", "street", "result"]
        )
        writer.writeheader()

        for record in reader:
            records_read += 1
            key = (
                (record["num"] or "").strip(),
                (record["zip"] or "").strip(),
                normalize_street(record["street"] or ""),
            )
            positions = lookup.get(key)
            if not positions:
                continue
            records_matched += 1
            for position in positions:
                # One old answer can serve several rows that share an address but sit
                # at different points; the answer is identical for all of them.
                if position in seen_positions:
                    continue
                seen_positions.add(position)
                num, street, zip_code = rows[position]
                writer.writerow(
                    {
                        "index": position,
                        # From the NEW parquet, so step2's validate_index_alignment
                        # compares equal.
                        "num": num,
                        "zip": zip_code,
                        "street": street,
                        "result": record["result"],
                    }
                )

    total = len(rows)
    print(
        f"read {records_read:,} scraped records, {records_matched:,} matched an address\n"
        f"wrote {len(seen_positions):,} of {total:,} addresses "
        f"({100 * len(seen_positions) / total:.2f}%)\n"
        f"{total - len(seen_positions):,} addresses have no scraped answer and will fall "
        f"back to the inferred polling areas",
        file=sys.stderr,
    )
    print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
