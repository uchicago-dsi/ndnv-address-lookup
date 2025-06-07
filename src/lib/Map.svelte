<script>
  import { MapLibre } from 'svelte-maplibre';
  import 'maplibre-gl/dist/maplibre-gl.css';

  import AddressLayer from './AddressesLayer.svelte';
  import mapStyle from '../data/map-style.json';

  // URL references in the map style JSON must be absolute
  mapStyle.sources.reservations = {
    type: "geojson",
    data: `${window.location.origin}/reservations.geojson`
  };
  mapStyle.sources.counties = {
    type: "geojson",
    data: `${window.location.origin}/counties.geojson`
  };
  mapStyle.sources.states = {
    type: "geojson",
    data: `${window.location.origin}/states.geojson`
  };

  let theMap;
  function handleOnLoad(map) {
    theMap = map;
  }

  export function flyTo(item) {
    if (theMap) {
      theMap.flyTo({ center: item.coords, zoom: item.zoom });
    }
  }
</script>

<MapLibre 
  class="map"
  style={mapStyle}
  standardControls
  pitchWithRotate={false}
  dragRotate={false}
  bounds={[-104.5181265794389, 45.63232713888373, -96.06887947161051, 49.2702273475217]}
  onload={handleOnLoad}
  >
  <AddressLayer />
</MapLibre>

<style>
  :global(.map) {
    height: 100vh;
    width: 100%;
  }
</style>
