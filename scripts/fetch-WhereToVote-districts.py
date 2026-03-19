#!/usr/bin/env python3

import argparse
import json
import re
import sys
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


BASE_URL = "https://vip.sos.nd.gov/WhereToVote.aspx"
HOUSE_INPUT_ID = "ctl00_ContentPlaceHolder1_txtHouseNumber"
ZIP_INPUT_ID = "ctl00_ContentPlaceHolder1_txtZip"
ADDRESS_SEARCH_BUTTON_ID = "ctl00_ContentPlaceHolder1_btnSearch"
ADDRESSES_GRID_ID = "ctl00_ContentPlaceHolder1_rgAddresses_ctl00"
ELECTION_DISTRICTS_TAB_ID = "ctl00_electionDistricts"


@dataclass
class AddressCandidate:
    part: str
    street: str
    city: str
    zip_code: str
    full_address: str
    select_name: str
    select_value: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--house-number", required=True, help="House number")
    parser.add_argument("--zip-code", required=True, help="ZIP code")
    parser.add_argument("--street", required=True, help="Street name without house number")
    parser.add_argument(
        "--stage",
        type=int,
        choices=(1, 2, 3),
        default=3,
        help="Stop after stage 1 (search), 2 (select), or 3 (district results)",
    )
    return parser.parse_args()


def normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())


def normalize_street(street: str) -> str:
    normalized = re.sub(r"[^0-9a-z]+", " ", street.casefold())
    tokens = normalized.split()
    replacements = {
        "street": "st",
        "road": "rd",
        "avenue": "ave",
        "boulevard": "blvd",
        "drive": "dr",
        "lane": "ln",
        "route": "rt",
    }
    collapsed = [replacements.get(token, token) for token in tokens]
    return " ".join(collapsed)


def get_form_fields(form: Tag) -> dict[str, str]:
    payload: dict[str, str] = {}
    for element in form.find_all(["input", "select", "textarea"]):
        name = element.get("name")
        if not name:
            continue
        tag_name = element.name.lower()
        if tag_name == "input":
            input_type = (element.get("type") or "text").lower()
            if input_type in {"submit", "button", "image", "file"}:
                continue
            if input_type in {"checkbox", "radio"} and not element.has_attr("checked"):
                continue
            payload[name] = element.get("value", "")
        elif tag_name == "textarea":
            payload[name] = element.get_text()
        elif tag_name == "select":
            selected = element.find("option", selected=True)
            if selected is None:
                selected = element.find("option")
            payload[name] = selected.get("value", "") if selected is not None else ""
    return payload


def get_form(soup: BeautifulSoup) -> Tag:
    form = soup.find("form", id="aspnetForm")
    if form is None:
        raise RuntimeError("Could not find aspnet form")
    return form


def stage1_search(
    session: requests.Session, house_number: str, zip_code: str
) -> tuple[requests.Response, BeautifulSoup]:
    response = session.get(BASE_URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    form = get_form(soup)
    payload = get_form_fields(form)

    house_input = form.find(id=HOUSE_INPUT_ID)
    zip_input = form.find(id=ZIP_INPUT_ID)
    button = form.find(id=ADDRESS_SEARCH_BUTTON_ID)
    if house_input is None or zip_input is None or button is None:
        raise RuntimeError("Could not find address search controls")

    house_name = house_input.get("name")
    zip_name = zip_input.get("name")
    button_name = button.get("name")
    if not house_name or not zip_name or not button_name:
        raise RuntimeError("Could not resolve field names for address search")

    payload[house_name] = house_number
    payload[zip_name] = zip_code
    payload[button_name] = button.get("value", "Search")

    action = form.get("action") or BASE_URL
    post_url = urljoin(response.url, action)
    search_response = session.post(post_url, data=payload, timeout=30)
    search_response.raise_for_status()
    return search_response, BeautifulSoup(search_response.text, "html.parser")


def parse_address_candidates(soup: BeautifulSoup) -> list[AddressCandidate]:
    table = soup.find("table", id=ADDRESSES_GRID_ID)
    if table is None:
        return []

    candidates: list[AddressCandidate] = []
    for row in table.select("tbody > tr"):
        cells = row.find_all("td")
        if len(cells) < 7:
            continue
        select_input = row.find("input", attrs={"type": "submit"})
        select_name = select_input.get("name") if select_input is not None else None
        if not select_name:
            continue
        candidates.append(
            AddressCandidate(
                part=cells[0].get_text(" ", strip=True),
                street=cells[1].get_text(" ", strip=True),
                city=cells[2].get_text(" ", strip=True),
                zip_code=cells[3].get_text(" ", strip=True),
                full_address=cells[4].get_text(" ", strip=True),
                select_name=select_name,
                select_value=select_input.get("value", "Select"),
            )
        )
    return candidates


def choose_candidate(
    candidates: list[AddressCandidate], house_number: str, street: str
) -> list[AddressCandidate]:
    target = normalize_street(f"{house_number} {street}")
    exact_matches = [
        candidate
        for candidate in candidates
        if normalize_street(candidate.street) == target
    ]
    if exact_matches:
        return exact_matches

    full_matches = [
        candidate
        for candidate in candidates
        if normalize_street(candidate.full_address).startswith(target)
    ]
    if full_matches:
        return full_matches

    available = ", ".join(candidate.street for candidate in candidates)
    raise RuntimeError(f"No address candidate matched '{target}'. Available: {available}")


def stage2_select(
    session: requests.Session,
    search_response: requests.Response,
    search_soup: BeautifulSoup,
    selected: AddressCandidate,
) -> tuple[requests.Response, BeautifulSoup]:
    form = get_form(search_soup)
    payload = get_form_fields(form)
    payload[selected.select_name] = selected.select_value

    action = form.get("action") or search_response.url
    post_url = urljoin(search_response.url, action)
    response = session.post(post_url, data=payload, timeout=30)
    response.raise_for_status()
    return response, BeautifulSoup(response.text, "html.parser")


def current_selected_tab(soup: BeautifulSoup) -> str | None:
    selected = soup.select_one("li.link-bk-Selected > a")
    return selected.get("id") if selected is not None else None


def stage3_go_to_districts(
    session: requests.Session, response: requests.Response, soup: BeautifulSoup
) -> tuple[requests.Response, BeautifulSoup]:
    if current_selected_tab(soup) == ELECTION_DISTRICTS_TAB_ID:
        return response, soup

    link = soup.find("a", id=ELECTION_DISTRICTS_TAB_ID)
    if link is None:
        raise RuntimeError("Could not find My Election Districts tab")

    href = link.get("href")
    if not href:
        raise RuntimeError("My Election Districts tab did not have an href")

    next_response = session.get(urljoin(response.url, href), timeout=30)
    next_response.raise_for_status()
    return next_response, BeautifulSoup(next_response.text, "html.parser")


def parse_district_pairs(soup: BeautifulSoup) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for row in soup.select("#ctl00_ContentPlaceHolder1_pnlDistricts table tr"):
        left = row.select_one("td.districtLeft label")
        right = row.select_one("td.districtRight label")
        if left is None or right is None:
            continue
        key = left.get_text(" ", strip=True).rstrip(":")
        value = right.get_text(" ", strip=True)
        if key:
            pairs.append((key, value))
    return pairs


def build_result(
    candidate: AddressCandidate, pairs: list[tuple[str, str]]
) -> dict[str, object]:
    return {
        "part": candidate.part,
        "street": candidate.street,
        "city": candidate.city,
        "zip_code": candidate.zip_code,
        "full_address": candidate.full_address,
        "districts": {key: value for key, value in pairs},
    }


def print_candidates(candidates: list[AddressCandidate]) -> None:
    for candidate in candidates:
        print(
            "\t".join(
                [
                    candidate.part,
                    candidate.street,
                    candidate.city,
                    candidate.zip_code,
                    candidate.full_address,
                ]
            )
        )


def main() -> int:
    args = parse_args()

    with requests.Session() as session:
        search_response, search_soup = stage1_search(
            session, args.house_number, args.zip_code
        )
        candidates = parse_address_candidates(search_soup)
        if not candidates:
            raise RuntimeError("Stage 1 did not reach the disambiguation page")

        if args.stage == 1:
            print_candidates(candidates)
            return 0

        matched_candidates = choose_candidate(
            candidates, args.house_number, args.street
        )
        if args.stage == 2:
            for selected in matched_candidates:
                detail_response, detail_soup = stage2_select(
                    session, search_response, search_soup, selected
                )
                _ = detail_response
                print(f"selected\t{selected.full_address}")
                title = (
                    detail_soup.title.get_text(" ", strip=True)
                    if detail_soup.title
                    else ""
                )
                tab = current_selected_tab(detail_soup) or "none"
                print(f"title\t{title}")
                print(f"selected_tab\t{tab}")
            return 0

        results: list[dict[str, object]] = []
        for selected in matched_candidates:
            detail_response, detail_soup = stage2_select(
                session, search_response, search_soup, selected
            )
            districts_response, districts_soup = stage3_go_to_districts(
                session, detail_response, detail_soup
            )
            _ = districts_response
            pairs = parse_district_pairs(districts_soup)
            if not pairs:
                raise RuntimeError(
                    f"Did not find any election district key-value pairs for {selected.full_address}"
                )
            results.append(build_result(selected, pairs))

        print(json.dumps(results, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.RequestException as err:
        print(f"Network error: {err}", file=sys.stderr)
        raise
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        raise
