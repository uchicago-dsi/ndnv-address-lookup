<script>
  import { getMapContext, GeoJSON, LineLayer, SymbolLayer } from 'svelte-maplibre';

  import { parquetMetadata, parquetRead } from "hyparquet";
  import { compressors } from "hyparquet-compressors";

  const MIN_ZOOM_FOR_ROADS = 13;

  let regions = [];
  let visibleIndexes = [];
  let forEachIndex = {};
  let parquetFile = null;
  const url = new URL("/osm-small-roads.parquet", import.meta.url).href;

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
        //          0        1        2       3      4      5
        columns: ["name", "fclass", "ref", "draw", "lon", "lat"],
        rowStart: regions[index].start,
        rowEnd: regions[index].stop,
        compressors,
        onComplete,
      })
    ).then(data => {
      forEachIndex[index.toString()] = data.map(row => {
        const ref = row[2];
        const i = ref === null ? -1 : ref.indexOf(" ");
        let ref_prefix = "";
        let ref_rest = "";
        if (i != -1) {
          ref_prefix = ref.substring(0, i);
          ref_rest = ref.substring(i + 1);
        }
        return {
          type: "Feature",
          geometry: {
            type: "LineString",
            coordinates: row[4].map((x, i) => [x, row[5][i]]),
          },
          properties: {
            name: row[0] === null ? "" : row[0],
            fclass: row[1],
            ref_prefix: ref_prefix,
            ref_rest: ref_rest,
            ref_length: ref === null ? 0 : ref.length,
            ref_rest_length: ref_rest.length,
            draw: row[3],
          },
        };
      });
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
      map.getSource("small-roads").setData({
        type: "FeatureCollection",
        features: visibleIndexes.map(i => forEachIndex[i] ?? []).flat(),
      });
    }
  }

  async function handleMove(event) {
    if (event.target.getZoom() >= MIN_ZOOM_FOR_ROADS) {
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

</script>

<GeoJSON
  id="small-roads"
  data={{type: "FeatureCollection", "features": []}}
  >

  <!-- highway-motorway-link -->
  <LineLayer
    filter={["all", ["in", "fclass", "motorway_link"], ["==", "draw", 1]]}
    minzoom={13}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#ffffff",
        "line-width": {
          "base": 1.2,
          "stops": [[13, 1], [13.5, 1.5], [14, 2.5], [20, 11.5]]
        }
      }}
    beforeLayerType="symbol"
  />

  <!-- highway-link -->
  <LineLayer
    filter={["all", ["in", "fclass", "primary_link", "secondary_link", "tertiary_link", "trunk_link"], ["==", "draw", 1]]}
    minzoom={13}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#ffffff",
        "line-width": {
          "base": 1.2,
          "stops": [[13, 1], [13.5, 1.5], [14, 2.5], [20, 11.5]]
        }
      }}
    beforeLayerType="symbol"
  />

  <!-- highway-minor (minor starts at 12) -->
  <LineLayer
    filter={["all", ["in", "fclass", "service", "residential", "unclassified", "footway", "path", "cycleway", "pedestrian", "steps", "bridleway", "living_street", "track", "track_grade1", "track_grade2", "track_grade3", "track_grade4", "track_grade5"], ["==", "draw", 1]]}
    minzoom={13}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#ffffff",
        "line-opacity": {
          "base": 0.5,
          "stops": [[13, 0], [13.5, 0.5], [20, 0.5]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[13, 1], [14, 2.5], [20, 11.5]]
        }
      }}
    beforeLayerType="symbol"
  />

  <!-- highway-secondary-tertiary (tertiary starts at 11) -->
  <LineLayer
    filter={["all", ["in", "fclass", "tertiary"], ["==", "draw", 1]]}
    minzoom={13}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#ffffff",
        "line-opacity": {
          "base": 0.5,
          "stops": [[13, 0], [13.5, 0.5], [20, 0.5]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[13, 1], [13.5, 0.5], [20, 13]]
        }
      }}
    beforeLayerType="symbol"
  />

  <!-- highway-name-path -->
  <SymbolLayer
    filter={["all", ["in", "fclass", "path"], ["!=", "name", ""]]}
    minzoom={15.5}
    layout={{
        "text-size": 13,
        "text-font": ["Noto Sans Regular"],
        "text-field": "{name}",
        "symbol-placement": "line",
        "text-rotation-alignment": "map"
      }}
    paint={{
        "text-color": "black",
        "text-halo-color": "white",
        "text-halo-blur": 0.5,
        "text-halo-width": 2
      }}
  />

  <!-- highway-name-minor -->
  <SymbolLayer
    filter={["all", ["in", "fclass", "service", "residential", "unclassified", "footway", "cycleway", "pedestrian", "steps", "bridleway", "living_street", "track", "track_grade1", "track_grade2", "track_grade3", "track_grade4", "track_grade5"], ["!=", "name", ""]]}
    minzoom={15}
    layout={{
        "text-size": 13,
        "text-font": ["Noto Sans Regular"],
        "text-field": "{name}",
        "symbol-placement": "line",
        "text-rotation-alignment": "map"
      }}
    paint={{
        "text-color": "black",
        "text-halo-color": "white",
        "text-halo-blur": 0.5,
        "text-halo-width": 2
      }}
  />

  <!-- highway-name-major -->
  <SymbolLayer
    filter={["all", ["in", "fclass", "primary", "secondary", "tertiary", "motorway", "trunk"], ["!=", "name", ""]]}
    minzoom={13}
    layout={{
        "text-size": 13,
        "text-font": ["Noto Sans Regular"],
        "text-field": "{name}",
        "symbol-placement": "line",
        "text-rotation-alignment": "map"
      }}
    paint={{
        "text-color": "black",
        "text-halo-color": "white",
        "text-halo-blur": 0.5,
        "text-halo-width": 2
      }}
  />

  <!-- highway-shield -->
  <SymbolLayer
    filter={["all", [">", "ref_length", 0], ["<=", "ref_length", 7], ["in", "ref_prefix", "CR", "BIA", "FS", "PTH", "PR", "TR", "CH"]]}
    minzoom={13}
    layout={{
        "text-size": 10,
        "icon-image": "road_{ref_length}",
        "icon-rotation-alignment": "viewport",
        "symbol-spacing": 200,
        "text-font": ["Noto Sans Regular"],
        "symbol-placement": "line",
        "text-rotation-alignment": "viewport",
        "icon-size": 1,
        "text-field": "{ref_prefix} {ref_rest}"
      }}
    paint={{
        "text-color": "rgba(0, 0, 0, 1)"
      }}
  />

  <!-- highway-shield-us-interstate -->
  <SymbolLayer
    filter={["all", [">", "ref_rest_length", 0], ["<=", "ref_rest_length", 3], ["in", "ref_prefix", "I"]]}
    minzoom={13}
    layout={{
        "text-size": 10,
        "icon-image": "us-interstate_{ref_rest_length}",
        "icon-rotation-alignment": "viewport",
        "symbol-spacing": 200,
        "text-font": ["Noto Sans Regular"],
        "symbol-placement": "line",
        "text-rotation-alignment": "viewport",
        "icon-size": 1,
        "text-field": "{ref_rest}"
      }}
    paint={{
        "text-color": "rgba(0, 0, 0, 1)"
      }}
  />

  <!-- highway-shield-us-other (network == "us-highway") -->
  <SymbolLayer
    filter={["all", [">", "ref_rest_length", 0], ["<=", "ref_rest_length", 3], ["in", "ref_prefix", "US"]]}
    minzoom={13}
    layout={{
        "text-size": 10,
        "icon-image": "us-highway_{ref_rest_length}",
        "icon-rotation-alignment": "viewport",
        "symbol-spacing": 200,
        "text-font": ["Noto Sans Regular"],
        "symbol-placement": "line",
        "text-rotation-alignment": "viewport",
        "icon-size": 1,
        "text-field": "{ref_rest}"
      }}
    paint={{
        "text-color": "rgba(0, 0, 0, 1)"
      }}
  />

  <!-- highway-shield-us-other (network == "us-state") -->
  <SymbolLayer
    filter={["all", [">", "ref_length", 0], ["<=", "ref_length", 6], ["in", "ref_prefix", "ND", "SD", "MT", "MN"]]}
    minzoom={13}
    layout={{
        "text-size": 10,
        "icon-image": "us-state_{ref_length}",
        "icon-rotation-alignment": "viewport",
        "symbol-spacing": 200,
        "text-font": ["Noto Sans Regular"],
        "symbol-placement": "line",
        "text-rotation-alignment": "viewport",
        "icon-size": 1,
        "text-field": "{ref_prefix} {ref_rest}"
      }}
    paint={{
        "text-color": "rgba(0, 0, 0, 1)"
      }}
  />

</GeoJSON>
