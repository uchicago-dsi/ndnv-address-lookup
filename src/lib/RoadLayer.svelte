<script>
  import { getMapContext, GeoJSON, LineLayer, SymbolLayer } from 'svelte-maplibre';

  import { getRoadData } from '../utils/getRoadData';

  let roads;
  const { map, loaded } = $derived(getMapContext());
  $effect(() => {
    // only load data and fill if the map is loaded and roads are empty
    if (loaded) {
      map.getSource("roads")?.getData().then((data) => {
        if (data.features.length == 0) {
          getRoadData().then((data) => {
            map.getSource("roads")?.setData(data);
          });
        }
      });
    }
  });

</script>

<GeoJSON
  id="roads"
  data={{type: "FeatureCollection", "features": []}}
  >

  <!-- highway-motorway-link-casing -->
  <LineLayer
    filter={["all", ["in", "fclass", "motorway_link"], ["==", "draw", 1]]}
    layout={{"line-cap": "butt", "line-join": "round"}}
    paint={{
        "line-color": "#e9ac77",
        "line-width": {
          "base": 1.2,
          "stops": [[12, 1], [13, 3], [14, 4], [20, 15]]
        }
      }}
  />

  <!-- highway-link-casing -->
  <LineLayer
    filter={["all", ["in", "fclass", "primary_link", "secondary_link", "tertiary_link", "trunk_link"], ["==", "draw", 1]]}
    layout={{"line-cap": "butt", "line-join": "round"}}
    paint={{
        "line-color": "#e9ac77",
        "line-width": {
          "base": 1.2,
          "stops": [[12, 1], [13, 3], [14, 4], [20, 15]]
        }
      }}
  />

  <!-- highway-minor-casing (minor starts at 12) -->
  <LineLayer
    filter={["all", ["in", "fclass", "service", "residential", "unclassified", "footway", "path", "cycleway", "pedestrian", "steps", "bridleway", "living_street", "track", "track_grade1", "track_grade2", "track_grade3", "track_grade4", "track_grade5"], ["==", "draw", 1]]}
    minzoom={12}
    layout={{"line-cap": "butt", "line-join": "round"}}
    paint={ {
        "line-color": "#cfcdca",
        "line-opacity": {
          "stops": [[12, 0], [12.5, 0]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[12, 0.5], [13, 1], [14, 4], [20, 15]]
        }
      }}
  />

  <!-- highway-secondary-tertiary-casing (tertiary starts at 11) -->
  <LineLayer
    filter={["all", ["in", "fclass", "tertiary"], ["==", "draw", 1]]}
    minzoom={10.5}
    layout={{"line-cap": "butt", "line-join": "round"}}
    paint={{
        "line-color": "#e9ac77",
        "line-opacity": {
          "base": 0.5,
          "stops": [[10.5, 0], [11.5, 0.5], [20, 0.5]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[8, 1.5], [20, 17]]
        }
      }}
  />

  <!-- highway-secondary-tertiary-casing (secondary starts at 9) -->
  <LineLayer
    filter={["all", ["in", "fclass", "secondary"], ["==", "draw", 1]]}
    minzoom={8.5}
    layout={{"line-cap": "butt", "line-join": "round"}}
    paint={{
        "line-color": "#e9ac77",
        "line-opacity": {
          "base": 0.5,
          "stops": [[8.5, 0], [9.5, 0.5], [20, 0.5]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[8, 1.5], [20, 17]]
        }
      }}
  />

  <!-- highway-primary-casing -->
  <LineLayer
    filter={["all", ["in", "fclass", "primary"], ["==", "draw", 1]]}
    minzoom={7}
    layout={{"line-cap": "butt", "line-join": "round"}}
    paint={{
        "line-color": "#e9ac77",
        "line-opacity": {
          "stops": [[7, 0], [8, 0.6]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[7, 0], [8, 0.6], [9, 1.5], [20, 22]]
        }
      }}
  />

  <!-- highway-trunk-casing -->
  <LineLayer
    filter={["all", ["in", "fclass", "trunk"], ["==", "draw", 1]]}
    minzoom={5}
    layout={{"line-cap": "butt", "line-join": "round"}}
    paint={{
        "line-color": "#e9ac77",
        "line-opacity": {
          "stops": [[5, 0], [6, 0.5]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[5, 0], [6, 0.6], [7, 1.5], [20, 22]]
        }
      }}
  />

  <!-- highway-motorway-casing -->
  <LineLayer
    filter={["all", ["in", "fclass", "motorway"], ["==", "draw", 1]]}
    minzoom={4}
    layout={{"line-cap": "butt", "line-join": "round"}}
    paint={{
        "line-color": "#e9ac77",
        "line-opacity": {
          "stops": [[4, 0], [5, 0.5]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[4, 0], [5, 0.4], [6, 0.6], [7, 1.5], [20, 22]]
        }
      }}
  />

  <!-- highway-motorway-link -->
  <LineLayer
    filter={["all", ["in", "fclass", "motorway_link"], ["==", "draw", 1]]}
    minzoom={12.5}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#fc8",
        "line-width": {
          "base": 1.2,
          "stops": [[12.5, 0], [13, 1.5], [14, 2.5], [20, 11.5]]
        }
      }}
  />

  <!-- highway-link -->
  <LineLayer
    filter={["all", ["in", "fclass", "primary_link", "secondary_link", "tertiary_link", "trunk_link"], ["==", "draw", 1]]}
    minzoom={12.5}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#fea",
        "line-width": {
          "base": 1.2,
          "stops": [[12.5, 0], [13, 1.5], [14, 2.5], [20, 11.5]]
        }
      }}
  />

  <!-- highway-minor (minor starts at 12) -->
  <LineLayer
    filter={["all", ["in", "fclass", "service", "residential", "unclassified", "footway", "path", "cycleway", "pedestrian", "steps", "bridleway", "living_street", "track", "track_grade1", "track_grade2", "track_grade3", "track_grade4", "track_grade5"], ["==", "draw", 1]]}
    minzoom={11.5}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#fff",
        "line-opacity": {
          "base": 0.5,
          "stops": [[11.5, 0], [12.5, 0.5], [20, 0.5]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[11.5, 0], [14, 2.5], [20, 11.5]]
        }
      }}
  />

  <!-- highway-secondary-tertiary (tertiary starts at 11) -->
  <LineLayer
    filter={["all", ["in", "fclass", "tertiary"], ["==", "draw", 1]]}
    minzoom={10.5}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#fea",
        "line-opacity": {
          "base": 0.5,
          "stops": [[10.5, 0], [11.5, 0.5], [20, 0.5]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[6.5, 0], [8, 0.5], [20, 13]]
        }
      }}
  />

  <!-- highway-secondary-tertiary (secondary starts at 9) -->
  <LineLayer
    filter={["all", ["in", "fclass", "secondary"], ["==", "draw", 1]]}
    minzoom={8.5}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#fea",
        "line-opacity": {
          "base": 0.5,
          "stops": [[8.5, 0], [9.5, 0.5], [20, 0.5]]
        },
        "line-width": {
          "base": 1.2,
          "stops": [[6.5, 0], [8, 0.5], [20, 13]]
        }
      }}
  />

  <!-- highway-primary -->
  <LineLayer
    filter={["all", ["in", "fclass", "primary"], ["==", "draw", 1]]}
    minzoom={8.5}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#fea",
        "line-opacity": 0.5,
        "line-width": {
          "base": 1.2,
          "stops": [[8.5, 0], [9, 0.5], [20, 18]]
        }
      }}
  />

  <!-- highway-trunk -->
  <LineLayer
    filter={["all", ["in", "fclass", "trunk"], ["==", "draw", 1]]}
    minzoom={4}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#fea",
        "line-opacity": 0.5,
        "line-width": {
          "base": 1.2,
          "stops": [[4, 0], [7, 0.5], [20, 18]]
        }
      }}
  />

  <!-- highway-motorway -->
  <LineLayer
    filter={["all", ["in", "fclass", "motorway"], ["==", "draw", 1]]}
    minzoom={4}
    layout={{"line-cap": "round", "line-join": "round"}}
    paint={{
        "line-color": "#fc8",
        "line-opacity": 0.5,
        "line-width": {
          "base": 1.2,
          "stops": [[4, 0], [7, 0.5], [20, 18]]
        }
      }}
  />

  <!-- highway-name-path -->
  <SymbolLayer
    filter={["all", ["in", "fclass", "path"], ["!=", "name", ""]]}
    minzoom={15.5}
    layout={{
        "text-size": {
          "base": 1,
          "stops": [[13, 12], [14, 13]]
        },
        "text-font": ["Noto Sans Regular"],
        "text-field": "{name}",
        "symbol-placement": "line",
        "text-rotation-alignment": "map"
      }}
    paint={{
        "text-color": "#15367d",
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
        "text-size": {
          "base": 1,
          "stops": [[13, 12], [14, 13]]
        },
        "text-font": ["Noto Sans Regular"],
        "text-field": "{name}",
        "symbol-placement": "line",
        "text-rotation-alignment": "map"
      }}
    paint={{
        "text-color": "#15367d",
        "text-halo-color": "white",
        "text-halo-blur": 0.5,
        "text-halo-width": 2
      }}
  />

  <!-- highway-name-major -->
  <SymbolLayer
    filter={["all", ["in", "fclass", "primary", "secondary", "tertiary", "motorway", "trunk"], ["!=", "name", ""]]}
    minzoom={12.2}
    layout={{
        "text-size": {
          "base": 1,
          "stops": [[13, 12], [14, 13]]
        },
        "text-font": ["Noto Sans Regular"],
        "text-field": "{name}",
        "symbol-placement": "line",
        "text-rotation-alignment": "map"
      }}
    paint={{
        "text-color": "#15367d",
        "text-halo-color": "white",
        "text-halo-blur": 0.5,
        "text-halo-width": 2
      }}
  />

  <!-- highway-shield -->
  <SymbolLayer
    filter={["all", [">", "ref_length", 0], ["<=", "ref_length", 7], ["in", "ref_prefix", "CR", "BIA", "FS", "PTH", "PR", "TR", "CH"]]}
    minzoom={10.5}
    layout={{
        "text-size": 10,
        "icon-image": "road_{ref_length}",
        "icon-rotation-alignment": "viewport",
        "symbol-spacing": 200,
        "text-font": ["Noto Sans Regular"],
        "symbol-placement": {
          "base": 1,
          "stops": [[10, "point"], [11, "line"]]
        },
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
    minzoom={7}
    layout={{
        "text-size": 10,
        "icon-image": "us-interstate_{ref_rest_length}",
        "icon-rotation-alignment": "viewport",
        "symbol-spacing": 200,
        "text-font": ["Noto Sans Regular"],
        "symbol-placement": {
          "base": 1,
          "stops": [[7, "point"], [7, "line"], [8, "line"]]
        },
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
    minzoom={9}
    layout={{
        "text-size": 10,
        "icon-image": "us-highway_{ref_rest_length}",
        "icon-rotation-alignment": "viewport",
        "symbol-spacing": 200,
        "text-font": ["Noto Sans Regular"],
        "symbol-placement": {
          "base": 1,
          "stops": [[10, "point"], [11, "line"]]
        },
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
    minzoom={9}
    layout={{
        "text-size": 10,
        "icon-image": "us-state_{ref_length}",
        "icon-rotation-alignment": "viewport",
        "symbol-spacing": 200,
        "text-font": ["Noto Sans Regular"],
        "symbol-placement": {
          "base": 1,
          "stops": [[10, "point"], [11, "line"]]
        },
        "text-rotation-alignment": "viewport",
        "icon-size": 1,
        "text-field": "{ref_prefix} {ref_rest}"
      }}
    paint={{
        "text-color": "rgba(0, 0, 0, 1)"
      }}
  />

</GeoJSON>
