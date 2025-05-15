<script lang="ts">
  import { onMount } from 'svelte'

  import { Map, Popup } from 'maplibre-gl';
  import 'maplibre-gl/dist/maplibre-gl.css';

  import { asyncBufferFromUrl, parquetReadObjects } from 'hyparquet';
  import { compressors } from 'hyparquet-compressors';

  import sourceList from './source-list.json';
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
          "src_title": sourceList[addr.src].title,
          "src_name": sourceList[addr.src].name,
          "src_phone": sourceList[addr.src].phone,
          "src_email": sourceList[addr.src].email
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

</script>

<style>
  .map {
    width: 100%;
    height: 100%;
  }
</style>

<div class="map" bind:this={mapContainer}></div>
