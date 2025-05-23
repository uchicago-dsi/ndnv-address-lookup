<script>
  import { getMapContext, GeoJSON, LineLayer, SymbolLayer } from 'svelte-maplibre';

  import { getWaterData } from '../utils/getWaterData';

  let roads;
  const { map, loaded } = $derived(getMapContext());
  $effect(() => {
    // only load data and fill if the map is loaded and water is empty
    if (loaded) {
      map.getSource("water")?.getData().then((data) => {
        if (data.features.length == 0) {
          getWaterData().then((data) => {
            map.getSource("water")?.setData(data);
          });
        }
      });
    }
  });

</script>

<GeoJSON
  id="water"
  data={{type: "FeatureCollection", "features": []}}
  >

  <LineLayer
    filter={["any", ["all", ["in", "fclass", "lake"], [">=", "area", 1000000]], ["in", "fclass", "river"]]}
    minzoom={9}
    paint={{
        "line-opacity": {
          "stops": [[9, 0], [10, 1]]
        },
        "line-color": "#237df2",
      }}
    beforeLayerType="symbol"
  />

  <LineLayer
    filter={["any", ["all", ["in", "fclass", "lake"], ["<", "area", 1000000]], ["!in", "fclass", "river", "lake"]]}
    minzoom={11}
    paint={{
        "line-opacity": {
          "stops": [[11, 0], [12, 1]]
        },
        "line-color": "#237df2",
      }}
    beforeLayerType="symbol"
  />

  <SymbolLayer
    filter={["all", ["any", ["all", ["in", "fclass", "lake"], [">=", "area", 1000000]], ["in", "fclass", "river"]], ["!=", "name", ""]]}
    minzoom={13}
    layout={{
        "text-size": {
          "base": 1,
          "stops": [[13, 12], [14, 13]]
        },
        "text-font": ["Noto Sans Bold"],
        "text-field": "{name}",
        "symbol-placement": "line",
        "text-rotation-alignment": "map"
      }}
    paint={{
        "text-color": "#237df2",
        "text-halo-color": "white",
        "text-halo-blur": 0.5,
        "text-halo-width": 1
      }}
  />

  <SymbolLayer
    filter={["all", ["any", ["all", ["in", "fclass", "lake"], ["<", "area", 1000000]], ["!in", "fclass", "river", "lake"]], ["!=", "name", ""]]}
    minzoom={15}
    layout={{
        "text-size": {
          "base": 1,
          "stops": [[15, 12], [16, 13]]
        },
        "text-font": ["Noto Sans Bold"],
        "text-field": "{name}",
        "symbol-placement": "line",
        "text-rotation-alignment": "map"
      }}
    paint={{
        "text-color": "#237df2",
        "text-halo-color": "white",
        "text-halo-blur": 0.5,
        "text-halo-width": 1
      }}
  />

</GeoJSON>
