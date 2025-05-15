<script>
  import { CircleLayer, MapLibre } from 'svelte-maplibre';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import { getAddressData } from '../utils/getAddressData';
  import GeoJsonSource from 'svelte-maplibre/GeoJSON.svelte';
  let addressData = getAddressData();
</script>

{#await addressData}
  <p>Loading...</p>
{:then addressData}
<MapLibre 
  center={[50,20]}
  zoom={7}
  class="map"
  standardControls
  style='/map-style.json'
  bounds={[-104.5181265794389, 45.63232713888373, -96.06887947161051, 49.2702273475217]}
>

  <GeoJsonSource
    id="addresses"
    data={addressData}
  >
    <CircleLayer
        id="address-circles"  
        source="addresses"
        minzoom={9}
        paint={{
          "circle-color": "hsl(214, 93%, 55%)",
          "circle-stroke-width": [
            "interpolate", ["linear"], ["zoom"], 9, 0, 12, 0.5, 17, 2
          ],
          "circle-stroke-color": "hsl(0, 15%, 100%)",
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"], 9, 2, 12, 3, 17, 8
          ]
        }}
    />
  </GeoJsonSource>
</MapLibre>
{:catch error}
  <p>Error loading data: {error.message}</p>
{/await}

<style>
  :global(.map) {
    height: 100vh;
    width:100%;
  }
</style>