<!-- <script lang="ts">
  import { onMount } from 'svelte'

  import { Map, Popup } from 'maplibre-gl';
  import copy_icon from './copy-icon.svg?raw';
  import copied_icon from './copied-icon.svg?raw';

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
    

    map.on("load", () => {
      map.addSource("addresses", {
        "type": "geojson",
        "data": addressesGeoJSON
      });
      map.addLayer({

      });
      map.on("click", "address-circles", (e) => {
        const coordinates = e.features[0].geometry.coordinates.slice();
        const addr = e.features[0].properties;
        const addrToCopy = `${addr.num >= 0 ? addr.num.toString() + " " : ""}${addr.street}, ${addr.muni != "Unincorporated" && addr.muni != "Undefined" ? addr.muni : addr.msag}, ND, ${addr.zip}`;
        const description = `
<span style="display: inline-flex; justify-content: center; width: 100%;" onclick='navigator.clipboard.writeText(${JSON.stringify(addrToCopy)}); this.innerHTML = ${JSON.stringify(copied_icon)};'>${copy_icon}</span><br>
<strong>Street Address:</strong> ${addr.num >= 0 ? addr.num : ""} ${addr.street}<br>
${addr.muni != "Unincorporated" && addr.muni != "Undefined" ? "<strong>Municipality:</strong> " + addr.muni + ", ND<br>" : ""}
${addr.muni != addr.msag ? "<strong>911 Community (MSAG):</strong> " + addr.msag + ", ND<br>" : ""}
<strong>Zip code:</strong> ${addr.zip}<br><br>
<details>
  <summary><strong>Source</strong></summary>
  <strong>${addr.src_title}</strong><br>
  <strong>Name:</strong> ${addr.src_name}<br>
  <strong>Phone:</strong> ${addr.src_phone}<br>
  <strong>Email:</strong> <a href="mailto:${addr.src_email}">${addr.src_email}</a>
</details>
`;

        new Popup({maxWidth: "none", closeButton: false})
          .setLngLat(coordinates)
          .setHTML(description)
          .addTo(map);
      });
      map.on("mouseenter", "address-circles", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "address-circles", () => {
        map.getCanvas().style.cursor = "";
      });
    });

  })();

</script> -->

<script>
  import Map from './lib/Map.svelte';
</script>
<Map />
