# Data re-check, 2026-09-02

Audit record for issue #34 / PR #35. All findings verified live on 2026-09-02 using the Chrome
DevTools MCP against the Secretary of State's ASP.NET/Telerik pages, the ND GIS Hub feature
service, `ndlegis.gov`, and the NDACo county officials directory.

Prompted by N.D.C.C. § 16.1-07-15: a county may change early voting up to the 64th day before an
election, which for November 3, 2026 was August 31, 2026. County decisions are now frozen.

## The headline finding: the app was serving the wrong election

`https://vip.sos.nd.gov/Precincts.aspx?eid=346` is the **June 9, 2026 primary**. The
**November 3, 2026 general election is `eid=348`**, per
<https://www.sos.nd.gov/elections/voter/elections-currentpast>.

Every shipped polling-place and drop-box file, and the `polling_places` column of
`911-addresses.parquet`, derived from `eid=346`. Meanwhile `WhereToVote.aspx` — the tool voters
are pointed at — now serves "2026 General Election" data matching `eid=348`. The app therefore
disagreed with the official source.

Verified example: `9298 18th St NW, Mandaree ND 58757` (McKenzie County, district 04, precinct
01, `smPrecinctPart` = `27040102`). WhereToVote lists Cartwright Hall, **Mandaree Community
Center** and Watford City City Hall. The shipped app omitted Mandaree Community Center, on the
Fort Berthold Reservation.

## Polling places

`eid=346` → `eid=348` (tab 5): 1,403 → 1,416 rows, 160 → 154 distinct locations, 391
`(county, district, precinct)` keys in both. **78 keys have a different set of locations:**

| County | Keys | Change |
|---|---|---|
| Cass | 34 | **+ Triumph West Church**, 3745 Sheyenne St S, West Fargo 58078 |
| Richland | 12 | **+ Lidgerwood KC Hall**, 56 Wiley Ave S, Lidgerwood 58053 |
| Dunn | 6 | **+ Dunn County Courthouse**, 205 Owens St, Manning (precincts 26/02–06, 39/02) |
| McKenzie | 2 | **+ Mandaree Community Center**, 212 Ridge Road, Mandaree 58757 — *Fort Berthold* |
| Williams | 24 | **Consolidated to Williston ARC alone.** Removed: Williams County Fairgrounds, Ernie French Center, Grenora City Hall, Ray City Hall, Tioga Community Center, Wildrose Fire Hall |

Plus **76 keys with hours-only changes** across Benson, Cavalier, Dickey, Divide, Grant, Griggs,
McHenry, Pierce, Ramsey, Stark, Walsh, Ward and Wells — mostly a 9:00AM or 8:00AM opening moving
to 7:00AM, and `MT`/`CT` suffixes added or removed.

One key added, one removed:

- **Added** `McLean|99|99 → Ralph Wells Community Center`, White Shield 58540. A pseudo-precinct
  (district 99 / precinct 99) that no real address maps to, so the pipeline ignores it. Ralph
  Wells already serves McLean 04/02, so White Shield voters lose nothing — confirmed by the app
  test.
- **Removed** `Ransom|24|01`. See below.

### Two counties the export omits

These are different cases and are handled differently.

**Ransom County — genuinely not established.** Absent from `eid=348` in both the polling-place
and drop-box tabs. `WhereToVoteDetail.aspx?Part=37240103` (304 Birch St, Lisbon) confirms it at
the source: *"This information has not been established at this time by the county. It will be
made available as soon as possible."* Its `eid=346` locations (EXPO in Lisbon, City Auditors
Office in Enderlin) were the primary's.

**Decision:** follow the official source. Ransom's ~2,591 addresses show no polling place rather
than a location the county has not confirmed for November. Recorded in
`scripts/precincts-supplement.json` under `counties_without_polling_places`, which makes step 2
drop them with a clear message instead of aborting. **To be re-checked every refresh.**

**Rolette County (Turtle Mountain) — published, but missing from the export.** Had 25 rows under
`eid=346` in April and zero under `eid=348`. But WhereToVote serves all five vote centers for all
five precincts under the "2026 General Election" heading (verified at `Part=40090101` through
`40090501`, identical sets, 11/03 8:00 AM–7:00 PM), plus a drop box. 7,340 of the state's
addresses are in Rolette County.

**Decision:** WhereToVote wins over the summary export's silence — it is the tool voters are sent
to and the source this whole model derives from. Restored via the `counties` section of
`scripts/precincts-supplement.json`, which appends a county only while the export lacks it and
prints a `SKIP supplement` warning once the state fixes it.

| Rolette vote center | Address |
|---|---|
| Derrick Dixon Event Center | 1210 William Hardesty Street, Belcourt 58316 |
| Dunseith City Hall | 13 1st St E, Dunseith 58329 |
| Rolla City Hall | 14 1st St SE, Rolla 58367 |
| St John Senior Center | 200 Foussard Ave SW, St. John 58369 |
| WWI Memorial Building | 503 2nd Ave, Rolette 58366 |
| Rolette County Courthouse (Drop Box) | 102 2nd St NE, Rolla 58367 |

Dunseith City Hall's address is taken from WhereToVote (`13 1st St E`); the April export said
`101 Peace Garden Ave`, which Google's address-verified place record contradicts. The two points
are 47 m apart — the same building — so the previously verified coordinate was kept.

### Mountrail County — caught only by the app regression test

Mountrail went from **8 polling places to 6**: Stanley High School Commons Area and White Earth
City Hall are gone. This did *not* appear in the `eid=346`-vs-`eid=348` diff, because `eid=346`
itself had drifted since April. It surfaced only when the rebuilt app was diffed against the
deployed site. Confirmed against WhereToVote (`Part=31020101`), which lists exactly six vote
centers. New Town and Parshall (Fort Berthold) are retained.

This is the strongest argument for keeping the production-diff step in the runbook.

## Drop boxes (tab 2): 58 → 62 rows

- **Added:** Dunn ("Drop Box", 205 Owens St, Manning), Mercer County Courthouse, Sargent County
  Courthouse, Walsh County Courthouse, **Sioux County Courthouse (Drop Box)**, **Sitting Bull
  College** (9299 Highway 24, Fort Yates), and Rolette County Courthouse via the supplement.
- **Removed:** Foster County Courthouse, Griggs County Courthouse, Ransom County Courthouse. The
  Foster and Griggs `eid=346` rows read "…by 7:00 PM June 9th, 2026" — primary-specific, correctly
  dropped, but with no general-election replacement entered yet.
- The two new Sioux entries serve Standing Rock.

A user-visible correction came with this: Adams County's drop-box text said ballots were due
"7:00 pm **November 9th**, 2026" — six days *after* the election. The state has since fixed it to
"November 3rd, 2026". Production still shows the wrong date.

## Early voting (tab 4) — 15 rows, newly surfaced in the app

Burleigh 1, Cass 5, Grand Forks 1, Morton 1, **Sioux 5**, Stark 1, Stutsman 1.

**Ward County is missing from `eid=348`** even though its `eid=346` comment described
general-election hours ("10am-6pm starting October 26th, 2026 thru October 30th, 2026 and on
November 2nd, 2026"). Another data-entry gap; omitted, following the source.

A nuance preserved deliberately: the admin tab says Sioux has `Early Voting = No`, yet the
early-voting tab lists five Sioux sites whose text reads "Absentee Voting Day – October 26th…".
These are absentee-voting events, not statutory early voting, and the same five sites also appear
as drop boxes. The app renders the state's own wording rather than relabelling them.

## Sioux County (Standing Rock) has no 911 data at all

Not just no addresses — **zero of 435,480 address points and zero of 175,283 road centerlines**.
`county_fp = 85` is absent from the Parquet (52 of 53 counties present) and `msag` has no rows
for Fort Yates, Cannon Ball, Selfridge, Porcupine or Twin Buttes.

Because drop boxes and early voting are filtered by the clicked address's `county_fp`, Standing
Rock voters previously saw **nothing at all** — not an address, not the 7 Sioux drop-box rows,
not the 5 absentee-voting sites.

Answering the question this raised: **Sioux County has exactly one election-day polling place**
— Sioux County Courthouse, 303 2nd Ave, Fort Yates 58538, 7:00AM–7:00PM — serving all three
precincts (31/01, 31/02, 31/03). The admin tab lists Sioux as `Vote Centers = Yes`,
`Traditional Precinct Polling Sites = No`, so no precinct restriction matters: every Sioux County
voter votes at the courthouse.

**Decision:** added a Sioux-County-only fallback (`src/lib/SiouxCountyDetailsContent.svelte`).
Tapping anywhere in the county — or searching "Sioux County" / "Standing Rock Reservation" —
opens a box with the address gap explained, the 911 coordinator, the polling place with the
vote-center explanation, all absentee/drop-box locations, driving directions from the tapped
point, and links to Legislative District 31, Ballotpedia and the SoS source. It reads the same
CSVs as the rest of the app, so it stays correct on the next refresh.

## 911 addresses refreshed: 431,238 → 435,480

The GIS Hub layer was last edited **2026-08-31**. Rebuilt from a fresh GeoPackage export.

The base-Parquet recipe had never been scripted. It was reverse-engineered from the April-2025
GeoPackage against the shipped file and is now `scripts/build-911-addresses.py`; running it on
the April-2025 input reproduces all nine base columns **identically and in order**, 206 row
groups with identical row counts. That regression test gates any future rebuild.

| | Before | After |
|---|---|---|
| Addresses | 431,238 | 435,480 (+4,242) |
| Official (in WhereToVote) | 88.5% | 86.5% (376,852) |
| Inferred from location | 11.5% | 13.5% (58,628) |
| No polling place at all | 848 | 3,681 (incl. Ransom's 2,591) |
| File size | 2,276,965 B | 2,318,040 B |
| Row groups | 206 | 206 |

The existing WhereToVote scrape was re-keyed rather than re-run (see the runbook, step 5e):
98.59% of addresses matched. Normalizing street names before matching recovered ~6,040 addresses
that raw matching would have dropped from an official answer to an inferred one — necessary
because the 2026 export spells out "Drive"/"Northeast" and mixed-cases names where the 2025
export was uppercase and abbreviated.

Two upstream schema changes handled:

- The GeoPackage layer was renamed `Structures_NG911` → `DBO_SiteStructureAddressPoints`
  (`--layer` option added).
- Cass County's `SOURCE` value changed `casscountynd.gov` → `CASS COUNTY 911`. Renamed **in
  place at index 54** of `source-list.json` so no `src` index shifts, with an alias in the build
  script so the historical regression test still runs.

## 911 coordinator contacts: 16 of 55 entries were stale

Diffed against the NDACo directory
(<https://www.ndaco.org/cod/browse-by-position/#/position/911%20Coordinator>). This is the contact
a voter uses when their address is wrong or missing, so it matters for the app's core purpose.
37 unchanged, 16 updated, 2 not in NDACo.

| # | County | Change |
|---|---|---|
| 0 | Adams | Jordan Fisher / 701-567-2530 → **Krista Faller / 701-567-4363 / kfaller@nd.gov** |
| 8 | Cavalier | Karen Kempert → **Amber Witzel / witzelamber@nd.gov** |
| 12 | Divide | 701-571-9218 → **701-965-6361** |
| 16 | Foster | 701-652-2252 → **701-251-6259**; still vacant; email now blank |
| 18 | Grand Forks | Chuck Marcott → **Kirsten Staples** |
| 20 | Griggs | Wayne Oien → **Makenzie Barclay** |
| 30 | Morton | `…@mortonnd.org` → **`…@mortonnd.gov`** |
| 33 | Oliver | "Ashley Hill & Kent Roth" → **Kent Roth** |
| 39 | Richland | Jill Breuer → **Tracy Hansen** |
| 41 | Sargent | Wendy Willprecht → **Wendy Schmiess** |
| 45 | Stark | Alaynea Decker → **Brad Banyai** |
| 46 | Steele | 701-524-2442 → **no phone listed** |
| 47 | Stutsman | Jessica Moser / 701-252-9093 → **Pam Blinsky / 701-251-6263** |
| 48 | Towner | lbeck@nd.gov → **tchd@gondtc.com** |
| 49 | Traill | Gerald Tollefson → **Ben Gates**; no phone listed |
| 50 | Walsh | Kristle Kjemhus → **Tim Newman** |

Foster's blank email and Steele's/Traill's blank phones were re-verified directly on the NDACo
page rather than assumed to be a parsing artifact. Each still has at least one contact channel.
The popup previously rendered `Phone:` and an empty `mailto:` link unconditionally; both are now
guarded.

Two further `title` fields were stale, found on a second pass that also diffed `title` (the first
pass compared only name/phone/email):

| # | County | Change |
|---|---|---|
| 33 | Oliver | "Oliver County 911 Coordinator**s**" → singular; the plural was left over from when the entry listed two people |
| 45 | Stark | "Stark County Emergency Services Director" → "Stark County 911 Coordinator"; the old role title belonged to the previous holder, and NDACo lists Brad Banyai as 911 Coordinator |

Williams County's title is legitimately not "911 Coordinator" — NDACo gives it as
"Executive Director of Williams County Dispatch Center", which is what the file already said.

### The two entries NDACo does not cover

Indices 9 and 10 are city rather than county authorities, so they are absent from the NDACo
directory. Both were verified directly against the cities' own websites on 2026-09-02 and both
are **correct as shipped**:

- **`CITY OF BISMARCK 911`** — Mike Dannenfelzer, CenCom Director, 701-255-5200,
  mdannenfelzer@bismarcknd.gov. All four fields confirmed on the City of Bismarck's Central
  Dakota Communications Center staff directory
  (<https://www.bismarcknd.gov/directory.aspx?did=5>). Note he is also Burleigh County's 911
  coordinator, at a different number (701-222-6727) — both entries are correct.
- **`CITY OF GRAND FORKS 911`** — 701-746-2566 and fire_admin@grandforksgov.com, both confirmed
  on the City of Grand Forks Fire Department administrative staff page
  (<https://www.grandforksgov.com/government/city-departments/fire/staff>). The `name` field is
  deliberately the placeholder "General questions, comments, and concerns" and the title records
  "(formerly 911 Coordinator)", because the city no longer staffs that role — an intentional
  choice by the original author, left as-is.

Incidental corroboration: that page lists the Grand Forks **Fire Chief as Charles Marcott** — the
same "Chuck Marcott" who was Grand Forks *County's* 911 coordinator in the old data. He changed
roles, which independently supports replacing him with Kirsten Staples at index 18.

**Net result: all 55 entries are now verified against a primary source** — 53 against NDACo and 2
against the cities directly — on name, phone, email and title.

## Verified unchanged — no action

- **Legislative districts.** `ndlegis.gov/districts` still lists 2025-2032 as current, and
  `HEAD` on `final-court-ordered-map-shape-files.zip` returns
  `last-modified: Tue, 28 May 2024 19:44:43 GMT` — the source file has not been touched since
  before the March 2026 fetch. Corroborated by `eid=348` using the same 48 districts and the same
  321 precincts. `legislative-districts.geojson`, `legislative-districts-exact.gpkg` and the
  Parquet's `district` column are unchanged, and the
  `ndlegis.gov/districts/2025-2032/district-N` popup links remain valid.
- **Counties.** 53 counties with unchanged numbers in every `eid=348` tab; North Dakota has had
  no boundary changes. `counties.geojson` / `counties-exact.gpkg` unchanged.
- **The WhereToVote scraper.** The form is structurally unchanged (`txtHouseNumber`, `txtZip`,
  `btnSearch`, `rgAddresses_ctl00`, `electionDistricts` all present; the hidden first grid column
  is still `smPrecinctPart`), so `scripts/step0-*` still work if a future rebuild needs them.
- **Roads, places, reservations, search indexes.** Not election-dependent; untouched apart from
  the `places.geojson` label fix below.

## Porcupine Local District Buidling — coordinate resolved to street level

Followed up after the initial pass. The Secretary of State gives the location as
`3457 Paha Yamni Loop, Porcupine, ND 58568`, and no geocoder resolves that house number.

Two plausible-looking sources are **wrong** and would each send a Standing Rock voter far away:

| Source | Coordinate | Error |
|---|---|---|
| Google name search ("Porcupine District Administration Building") | 43.240, -102.330 | Porcupine, **South Dakota** — Pine Ridge, ~350 km |
| MapQuest "Porcupine Local District" (`streetAddress: null`) | 46.040379, -100.922115 | **Selfridge, ND** — 24.1 km, and 256 m from the Selfridge Senior Center |

Root cause of the MapQuest error: ZIP **58568**'s postal locality is Selfridge, and Porcupine
shares that ZIP. Google labels the street itself "Paha Yamni Loop, **Selfridge**, North Dakota"
even while its minimap says "Porcupine". Any geocoder that resolves the ZIP to a city lands in
Selfridge, 24 km from the actual community.

What was verified instead: Paha Yamni Loop is a real street in Porcupine (Google street labels,
plus Sep 2024 Street View coverage whose minimap reads "Porcupine"). At the centre of the loop
there is exactly one institutional building among roughly twenty houses — gymnasium-scale,
metal-clad with a painted hills mural, a solar array and a large parking lot. Wikipedia's
Porcupine CDP entry notes the community "includes the headquarters of the Selfridge/Porcupine
district", corroborating the state's address over MapQuest's.

Shipped coordinate: `-101.0960593, 46.2204509` — the Street View camera position on Paha Yamni
Loop immediately beside that building. Being a point on the road, it is a good directions
destination. **Street-level confidence: no sign is legible from any available angle and no source
resolves house number 3457, so the building's identity is inferred from context.** Recorded in
`known-gaps.md`; a building-level confirmation needs the Sioux County auditor.

## Smaller fixes

- `polling-places-locations.json` had **no coordinate for
  `Ward County Administration Building - 1st Floor Meeting Rooms 105, 106 & 108`**, the largest
  polling place in Minot, so it rendered with no directions link. Recovered from the
  same-address drop-box entry.
- `places.geojson`'s FeatureCollection was mislabelled `"name": "reservations"` → `"places"`.
- `scripts/step0-batch-fetch-WhereToVote-districts.py` pointed at the pre-rename
  `fetch-WhereToVote-districts.py`.
- Twelve renamed locations reused their existing manually-verified coordinates by matching on
  address rather than name, preserving that verification work.
- Three geocoded coordinates were corrected after visual checks (see the runbook, step 4).
- `scripts/step3-…` now pins `FINAL_COLUMN_ORDER`. The rebuild had produced a different column
  order, which matters because `AddressesLayer.svelte` reads the Parquet by name and then indexes
  the result **positionally**.

## Verification performed

- `build-911-addresses.py --verify-against` the April-2025 snapshot: nine base columns identical
  in order, 206 row groups with identical counts.
- `validate-data.py`: schema, column order, types, row-group count, per-row-group lon/lat
  statistics, encodings, compression, `polling_places` index range, `src` range, name→address
  uniqueness, coordinates inside North Dakota. Zero errors; four expected warnings.
- Rebuilt Parquet is structurally identical to the shipped one: same column order, types,
  per-column encodings, compression and row-group layout.
- App tested on the production build with the Chrome DevTools MCP: all nine changed-data cases
  above, plus regression diffs against the deployed site for Pembina, Adams and Mountrail; the
  Sioux box; the mobile `<dialog>` path at 360×640 and 320×480; double-tap and state-isolation
  behaviour; console clean apart from the pre-existing `Unimplemented type: 4`.
- `svelte-check` unchanged at the codebase's standing 195 errors.
- Memory returns to 39–41 MB after collection, with no DOM retained across 40 open/close cycles.
