<script lang="ts">
  import { onMount } from 'svelte'

  import { Map } from 'maplibre-gl';
  import 'maplibre-gl/dist/maplibre-gl.css';

  import { asyncBufferFromUrl, parquetReadObjects } from 'hyparquet';
  import { compressors } from 'hyparquet-compressors';

  import sourceList from './source-list.json';

  let map;
  let mapContainer;
  onMount(() => {
    map = new Map({
      container: mapContainer,
      style: "/map-style.json",
      bounds: [-104.5181265794389, 45.63232713888373, -96.06887947161051, 49.2702273475217],
    });
  });

  let addresses;
  let addressesGeoJSON;
  (async () => {
    const url = "http://localhost:5173/911-addresses.parquet";
    const file = await asyncBufferFromUrl({ url });
    addresses = await parquetReadObjects({ file, compressors });

    addressesGeoJSON = {
      "type": "FeatureCollection",
      "features": addresses.map(addr => ({
        "type": "Feature",
        "geometry": {
          "type": "Point",
          "coordinates": [addr.lon, addr.lat]
        },
        "properties": {
          "num": addr.num,
          "street": addr.street,
          "muni": addr.muni,
          "msag": addr.msag,
          "zip": addr.zip,
          "src": sourceList[addr.src]
        }
      }))
    };

    map.on("load", () => {
      map.addSource("addresses", {
        "type": "geojson",
        "data": addressesGeoJSON
      });
      map.addLayer({
        "id": "address-circles",
        "type": "circle",
        "source": "addresses",
        "minzoom": 9,
        "paint": {
          "circle-color": "hsl(214, 93%, 55%)",
          "circle-stroke-width": [
            "interpolate", ["linear"], ["zoom"], 9, 0, 12, 0.5, 17, 2
          ],
          "circle-stroke-color": "hsl(0, 15%, 100%)",
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"], 9, 2, 12, 3, 17, 8
          ]
        }
      });
    });

  })();

</script>

<style>
  .map {
    width: 100%;
    height: 100%;
  }
</style>

<div class="map" bind:this={mapContainer}></div>
