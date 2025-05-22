<script>
  import { getMapContext, GeoJSON } from 'svelte-maplibre';

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
</GeoJSON>
