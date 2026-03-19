<script>
  import { getMapContext, GeoJSON, CircleLayer, Popup } from 'svelte-maplibre';

  import sourceList from "../data/source-list.json";
  import { parquetMetadata, parquetRead } from "hyparquet";
  import { compressors } from "hyparquet-compressors";

  const MIN_ZOOM_FOR_POINTS = 11;

  let regions = [];
  let visibleIndexes = [];
  let forEachIndex = {};
  let parquetFile = null;
  const url = new URL("/911-addresses.parquet", import.meta.url).href;
  const pollingPlacesUrl = new URL("/polling-places-nodups.csv", import.meta.url).href;
  const pollingPlaceLocationsUrl = new URL("/polling-places-locations.json", import.meta.url).href;
  let pollingPlaces = [];
  let pollingPlaceLocations = {};

  function parseCsv(text) {
    let rows = [];
    let row = [];
    let field = "";
    let inQuotes = false;

    for (let i = 0;  i < text.length;  i++) {
      const char = text[i];
      const next = text[i + 1];

      if (inQuotes) {
        if (char == '"'  &&  next == '"') {
          field += '"';
          i += 1;
        }
        else if (char == '"') {
          inQuotes = false;
        }
        else {
          field += char;
        }
      }
      else if (char == '"') {
        inQuotes = true;
      }
      else if (char == ",") {
        row.push(field);
        field = "";
      }
      else if (char == "\n") {
        row.push(field);
        rows.push(row);
        row = [];
        field = "";
      }
      else if (char != "\r") {
        field += char;
      }
    }

    if (field != ""  ||  row.length != 0) {
      row.push(field);
      rows.push(row);
    }

    const headers = rows[0] ?? [];
    return rows.slice(1).map(values =>
      Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]))
    );
  }

  function hasNewIndexes(newVisibleIndexes) {
    if (newVisibleIndexes.length > visibleIndexes.length) {
      return true;
    }
    let oldi = 0;
    let newi = 0;
    while (oldi < visibleIndexes.length  &&  newi < newVisibleIndexes.length) {
      if (visibleIndexes[oldi] < newVisibleIndexes[newi]) {
        oldi += 1;
      }
      else if (visibleIndexes[oldi] == newVisibleIndexes[newi]) {
        oldi += 1;
        newi += 1;
      }
      else {
        return true;
      }
    }
    return newi < newVisibleIndexes.length;
  }

  async function readFromParquet(index) {
    return new Promise((onComplete) =>
      parquetRead({
        file: parquetFile,
        //          0        1        2       3       4      5      6      7           8      9      10                11
        columns: ["num", "street", "unit", "muni", "msag", "zip", "src", "district", "lon", "lat", "in_wheretovote", "polling_places"],
        rowStart: regions[index].start,
        rowEnd: regions[index].stop,
        compressors,
        onComplete,
      })
    ).then(data => {
      forEachIndex[index.toString()] = data.map(row => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [row[8], row[9]],
        },
        properties: {
          num: row[0],
          street: row[1],
          unit: row[2],
          muni: row[3],
          msag: row[4],
          zip: row[5],
          src: row[6],
          district: row[7],
          lon: row[8],
          lat: row[9],
          in_wheretovote: row[10],
          polling_places: row[11],
        },
      }));
    });
  }

  const { map, loaded } = $derived(getMapContext());
  $effect(() => {
    if (loaded) {
      map.on("zoom", handleMove);
      map.on("move", handleMove);
    }
  });

  function reloadSource() {
    if (loaded) {
      map.getSource("addresses").setData({
        type: "FeatureCollection",
        features: visibleIndexes.map(i => forEachIndex[i] ?? []).flat(),
      });
    }
  }

  async function handleMove(event) {
    if (event.target.getZoom() >= MIN_ZOOM_FOR_POINTS) {
      const bounds = event.target.getBounds();
      const west = bounds.getWest();
      const east = bounds.getEast();
      const south = bounds.getSouth();
      const north = bounds.getNorth();

      let newVisibleIndexes = [];
      for (let i = 0;  i < regions.length;  i++) {
        const r = regions[i];
        if (r.east >= west  &&  r.west <= east  &&  r.north >= south  &&  r.south <= north) {
          newVisibleIndexes.push(i);
        }
      }

      if (hasNewIndexes(newVisibleIndexes)  &&  parquetFile !== null) {
        visibleIndexes = newVisibleIndexes;

        for (const index in forEachIndex) {
          if (!(Number(index) in visibleIndexes)) {
            delete forEachIndex[index];
          }
        }

        let promises = [];
        for (const index of visibleIndexes) {
          if (!(index.toString() in forEachIndex)) {
            promises.push(readFromParquet(index));
          }
        }
        Promise.all(promises).then(reloadSource).catch(reloadSource);
      }
    }
  }

  fetch(url).then(async response => {
    if (!response.ok) {
      return;
    }
    parquetFile = await response.arrayBuffer();

    const metadata = parquetMetadata(parquetFile);

    let start = 0;
    for (const rg of metadata.row_groups) {
      let lonStats = rg.columns.filter(x => x.meta_data.path_in_schema[0] == "lon")[0].meta_data.statistics;
      let latStats = rg.columns.filter(x => x.meta_data.path_in_schema[0] == "lat")[0].meta_data.statistics;

      const stop = start + Number(rg.num_rows);
      regions.push({
        start: start,
        stop: stop,
        west: lonStats.min_value,
        east: lonStats.max_value,
        south: latStats.min_value,
        north: latStats.max_value,
      });
      start = stop;
    }
  });

  fetch(pollingPlacesUrl).then(async response => {
    if (!response.ok) {
      return;
    }
    pollingPlaces = parseCsv(await response.text());
  });

  fetch(pollingPlaceLocationsUrl).then(async response => {
    if (!response.ok) {
      return;
    }
    pollingPlaceLocations = await response.json();
  });

  function mouseEnter(event) {
    event.map.getCanvas().style.cursor = "pointer";
  }
  
  function mouseLeave(event) {
    event.map.getCanvas().style.cursor = "";
  }

  let popupData = $state(null);
  let popupAbsorbFocus = null;
  let popupCopyButton = null;
  let popupCopiedMessage = null;

  function handleClick(event) {
    let p = event.features[0].properties;
    let isMuni = p.muni != "Unincorporated"  &&  p.muni != "Undefined";
    let unit = p.unit == "" ? "" : ` (${p.unit})`;
    popupData = {
      streetAddressHeader: p.unit == "" ? "Street address" : "Street address (and unit)",
      streetAddress: (p.num >= 0 ? p.num.toString() + " " : "") + p.street + unit,
      cityHeader: isMuni ? "Municipality" : "911 Community (MSAG)",
      city: isMuni ? p.muni : p.msag,
      zip: p.zip,
      district: p.district?.trim?.() ?? "",
      lon: p.lon,
      lat: p.lat,
      in_wheretovote: p.in_wheretovote,
      polling_places: p.polling_places,
      src_title: sourceList[p.src].title,
      src_name: sourceList[p.src].name,
      src_phone: sourceList[p.src].phone,
      src_email: sourceList[p.src].email
    };
    popupData.addrToCopy = `${popupData.streetAddress}, ${popupData.city}, ND, ${popupData.zip}`;

    if (popupCopyButton !== null  &&  popupCopiedMessage !== null) {
      popupCopyButton.style.display = "";
      popupCopiedMessage.style.display = "none";
    }
  }

  const REVERT_COPY_BUTTON_TIMEOUT = 10000;

  function copyAddress(text) {
    navigator.clipboard.writeText(text);
  }

  function handleCopy(event) {
    copyAddress(popupData.addrToCopy);
    if (popupCopyButton !== null  &&  popupCopiedMessage !== null) {
      popupCopyButton.style.display = "none";
      popupCopiedMessage.style.display = "";
      setTimeout(() => {
        popupCopyButton.style.display = "";
        popupCopiedMessage.style.display = "none";
      }, REVERT_COPY_BUTTON_TIMEOUT);
    }
  }

  function handleBallotpediaLookup(event) {
    copyAddress(`${popupData.addrToCopy}, USA`);
  }

  function handleWhereToVoteLookup(event) {
    let houseNumber = popupData?.streetAddress.match(/^\d+/)?.[0] ?? "";
    copyAddress(houseNumber);
  }

  function list_polling_places(popupData) {
    if (popupData?.polling_places == "") {
      return "";
    }

    const origin = `${popupData?.lat},${popupData?.lon}`;
    let rows = popupData.polling_places
      .split(" ")
      .map(x => Number(x))
      .filter(x => Number.isInteger(x)  &&  x >= 0  &&  x < pollingPlaces.length)
      .map(x => pollingPlaces[x])
      .map(place => {
        const coordinates = pollingPlaceLocations[place.polling_location];
        const destination = Array.isArray(coordinates)  &&  coordinates.length == 2
          ? `${coordinates[1]},${coordinates[0]}`
          : null;
        const addressLine = `${place.address}, ${place.city} ${place.zip_code}`;

        if (destination === null) {
          return `${place.polling_location}<br>${addressLine}<br>(${place.polling_hours}, ${place.county_auditor_phone})`;
        }

        const url = "https://www.google.com/maps/dir/?api=1"
          + `&origin=${encodeURIComponent(origin)}`
          + `&destination=${encodeURIComponent(destination)}`
          + "&travelmode=driving";
        return `${place.polling_location}<br><a href="${url}" target="_blank" rel="noreferrer">${addressLine}</a><br>(${place.polling_hours}, ${place.county_auditor_phone})`;
      })
      .join("<br><br>");

    if (popupData?.in_wheretovote) {
      return `<br><br><details><summary><strong>Polling Places (from WhereToVote)</strong></summary>${rows}</details>`;
    }
    else {
      return `<br><br><details><summary><strong>Polling Places (inferred from location)</strong></summary>${rows}</details>`;
    }
  }

</script>

<GeoJSON
  id="addresses"
  data={{type: "FeatureCollection", "features": []}}
  attribution={'<a target="_blank" href="https://gishubdata-ndgov.hub.arcgis.com/datasets/NDGOV::ndgishub-site-structure-address-points/about">North Dakota 911 address dataset</a>'}
  >
  <CircleLayer
    id="address-circles"
    source="addresses"
    onmouseenter={mouseEnter}
    onmouseleave={mouseLeave}
    onclick={handleClick}
    minzoom={MIN_ZOOM_FOR_POINTS}
    paint={{
        "circle-color": "#5ef2de",
        "circle-stroke-width": [
          "interpolate", ["linear"], ["zoom"], 11, 0, 13, 0.5, 17, 2
        ],
        "circle-stroke-color": "black",
        "circle-radius": [
          "interpolate", ["linear"], ["zoom"], MIN_ZOOM_FOR_POINTS, 0, 13, 3, 17, 8
        ],
        "circle-stroke-opacity": {
          "base": 1,
          "stops": [[11, 0], [13, 1], [20, 1]]
        },
        "circle-opacity": {
          "base": 1,
          "stops": [[MIN_ZOOM_FOR_POINTS, 0], [MIN_ZOOM_FOR_POINTS + 1, 1], [20, 1]]
        }
      }}
    beforeLayerType="symbol"
  >
    <Popup>
      <div style="margin-bottom: 10px;">
        <span class="popupCopyButton">
          <!-- always hidden, takes the focus so that the copy button doesn't -->
          <button type="button" bind:this={popupAbsorbFocus} style="display: none;"></button>

          <!-- the "copy" button and "copied" message toggle "display: none;" -->
          <button type="button" bind:this={popupCopyButton} onclick={handleCopy}>Copy to Clipboard</button>
          <span bind:this={popupCopiedMessage} style="display: none;">Copied!</span>

        </span>
      </div>
      <div style="color: black;">
        <strong>{popupData?.streetAddressHeader}:</strong> {popupData?.streetAddress}<br>
        <strong>{popupData?.cityHeader}:</strong> {popupData?.city}<br>
        <strong>Zip code:</strong> {popupData?.zip}<br>
          <details>
          <summary><strong>Source</strong></summary>
          <strong>{popupData?.src_title}</strong><br>
          <strong>Name:</strong> {popupData?.src_name}<br>
          <strong>Phone:</strong> {popupData?.src_phone}<br>
          <strong>Email:</strong> <a href="mailto:{popupData?.src_email}">{popupData?.src_email}</a>
        </details>
        <br>
        <a
          href="https://ndlegis.gov/districts/2025-2032/district-{popupData.district.replace(/[AB]$/, '')}"
          target="_blank"
          rel="noreferrer"
        >Legislative District {popupData.district}</a>
        <br>
        <a
          href="https://ballotpedia.org/Sample_Ballot_Lookup"
          target="_blank"
          rel="noreferrer"
          onclick={handleBallotpediaLookup}
        >Copy address and go to Ballotpedia</a>
        <br>
        <a
          href="https://vip.sos.nd.gov/WhereToVote.aspx"
          target="_blank"
          rel="noreferrer"
          onclick={handleWhereToVoteLookup}
        >Copy number and go to WhereToVote</a>{@html list_polling_places(popupData)}
      </div>
    </Popup>
  </CircleLayer>
</GeoJSON>

<style>
  .popupCopyButton {
    display: inline-flex;
    justify-content: center;
    width: 100%;
  }
  :global(.popupCopyButton button) {
    border: 1px solid #808080;
    background: #f0f0f0;
    color: black;
    font-weight: bold;
  }
  :global(.popupCopyButton span) {
    margin-top: 6px;
    margin-bottom: 5px;
    background: white;
    color: black;
    font-weight: bold;
  }
</style>
