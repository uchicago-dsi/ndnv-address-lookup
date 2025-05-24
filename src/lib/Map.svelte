<script>
  import { MapLibre } from 'svelte-maplibre';
  import 'maplibre-gl/dist/maplibre-gl.css';

  import AddressLayer from './AddressesLayer.svelte';
  import RoadLayer from './RoadLayer.svelte';
  import WaterLayer from './WaterLayer.svelte';
  import mapStyle from '../data/map-style.json';

  // URL references in the map style JSON must be absolute
  mapStyle.sprite = `${window.location.origin}/sprites`;
  mapStyle.glyphs = `${window.location.origin}/fonts/{fontstack}/{range}.pbf`;
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
  mapStyle.sources.places = {
    type: "geojson",
    data: `${window.location.origin}/osm-places.geojson`
  };

</script>

<MapLibre 
  class="map"
  style={mapStyle}
  standardControls
  bounds={[-104.5181265794389, 45.63232713888373, -96.06887947161051, 49.2702273475217]}
  >
  <WaterLayer />
  <RoadLayer />
  <AddressLayer />
</MapLibre>

<style>
  :global(.map) {
    height: 100vh;
    width: 100%;
  }
</style>
