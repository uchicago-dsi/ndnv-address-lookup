<script>
  import { MapLibre } from 'svelte-maplibre';
  import 'maplibre-gl/dist/maplibre-gl.css';

  import SmallRoadLayer from './SmallRoadLayer.svelte';
  import AddressLayer from './AddressesLayer.svelte';
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
  mapStyle.sources["big-roads"] = {
    type: "geojson",
    data: `${window.location.origin}/osm-big-roads.geojson`
  };
  mapStyle.sources["places"] = {
    type: "geojson",
    data: `${window.location.origin}/places.geojson`
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

  const MAP_BOUNDS = [-104.5181265794389, 45.63232713888373, -96.06887947161051, 49.2702273475217];
  const DX = 0.5 * (MAP_BOUNDS[2] - MAP_BOUNDS[0]);
  const DY = 0.5 * (MAP_BOUNDS[3] - MAP_BOUNDS[1]);
  const MAP_MAX_BOUNDS = [MAP_BOUNDS[0] - DX, MAP_BOUNDS[1] - DY, MAP_BOUNDS[2] + DX, MAP_BOUNDS[3] + DY]
</script>

<MapLibre 
  class="map"
  style={mapStyle}
  standardControls
  pitchWithRotate={false}
  dragRotate={false}
  bounds={MAP_BOUNDS}
  maxBounds={MAP_MAX_BOUNDS}
  onload={handleOnLoad}
  >
  <SmallRoadLayer />
  <AddressLayer />
</MapLibre>

<style>
  :global(.map) {
    height: 100vh;
    width: 100%;
  }
</style>
