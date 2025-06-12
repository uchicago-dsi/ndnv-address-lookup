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
        //          0        1        2       3       4      5      6      7      8
        columns: ["num", "street", "unit", "muni", "msag", "zip", "src", "lon", "lat"],
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
          coordinates: [row[7], row[8]],
        },
        properties: {
          num: row[0],
          street: row[1],
          unit: row[2],
          muni: row[3],
          msag: row[4],
          zip: row[5],
          src: row[6],
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
      streetAddress: (p.num >= 0 ? p.num.toString() + " " : "") + p.street + unit,
      cityHeader: isMuni ? "Municipality" : "911 Community (MSAG)",
      city: isMuni ? p.muni : p.msag,
      zip: p.zip,
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

  function handleCopy(event) {
    navigator.clipboard.writeText(popupData.addrToCopy);
    if (popupCopyButton !== null  &&  popupCopiedMessage !== null) {
      popupCopyButton.style.display = "none";
      popupCopiedMessage.style.display = "";
      setTimeout(() => {
        popupCopyButton.style.display = "";
        popupCopiedMessage.style.display = "none";
      }, REVERT_COPY_BUTTON_TIMEOUT);
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
        <strong>Street address:</strong> {popupData?.streetAddress}<br>
        <strong>{popupData?.cityHeader}:</strong> {popupData?.city}<br>
        <strong>Zip code:</strong> {popupData?.zip}<br><br>
          <details>
          <summary><strong>Source</strong></summary>
          <strong>{popupData?.src_title}</strong><br>
          <strong>Name:</strong> {popupData?.src_name}<br>
          <strong>Phone:</strong> {popupData?.src_phone}<br>
          <strong>Email:</strong> <a href="mailto:{popupData?.src_email}">{popupData?.src_email}</a>
        </details>
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
