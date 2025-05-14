<script lang="ts">
  import { onMount } from 'svelte'
  import { Map } from 'maplibre-gl';
  import 'maplibre-gl/dist/maplibre-gl.css';

  let map;
  let mapContainer;

  onMount(() => {
    map = new Map({
      container: mapContainer,
      style: "https://raw.githubusercontent.com/go2garret/maps/main/src/assets/json/arcgis_hybrid.json",
      bounds: [-104.5181265794389, 45.63232713888373, -96.06887947161051, 49.2702273475217],
    });
  });

</script>

<style>
  .map {
    width: 100%;
    height: 100%;
  }
</style>

<div class="map" bind:this={mapContainer}></div>
