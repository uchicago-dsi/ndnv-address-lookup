<script>
  import { Map, NavigationControl, ScaleControl, FullscreenControl, Popup } from 'mapbox-gl';
  import 'mapbox-gl/dist/mapbox-gl.css';
  import { onMount } from 'svelte';

  import sourceList from "../data/source-list.json";
  import copyIcon from '../assets/copy-icon.svg?raw';
  import copiedIcon from '../assets/copied-icon.svg?raw'

  let map;
  let mapContainer;

  function getPopupData(p) {
    let isMuni = p.muni != "Unincorporated"  &&  p.muni != "Undefined";
    let popupData = {
      streetAddress: (p.num >= 0 ? p.num.toString() + " " : "") + `${p.street}, ${isMuni ? p.muni : p.msag}`,
      cityHeader: isMuni ? "Municipality" : "911 Community (MSAG)",
      city: isMuni ? p.muni : p.msag,
      zip: p.zip,
      src_title: sourceList[p.srcIndex].title,
      src_name: sourceList[p.srcIndex].name,
      src_phone: sourceList[p.srcIndex].phone,
      src_email: sourceList[p.srcIndex].email
    };
    popupData.addrToCopy = `${popupData.streetAddress}, ${popupData.city}, ND, ${popupData.zip}`;
    return popupData;
  }

  function popupHTML(properties) {
    const popupData = getPopupData(properties);

    return `
      <span
        class="popupCopyButton"
        onclick='navigator.clipboard.writeText(${JSON.stringify(popupData.addrToCopy)}); this.innerHTML = ${JSON.stringify(copiedIcon)};'
        style="display: inline-flex; justify-content: center; width: 100%;"
        >${copyIcon}</span><br>
      <strong>Street address:</strong> ${popupData?.streetAddress}<br>
      <strong>${popupData?.cityHeader}:</strong> ${popupData?.city}<br>
      <strong>Zip code:</strong> ${popupData?.zip}<br><br>
      <details>
        <summary><strong>Source</strong></summary>
        <strong>${popupData?.src_title}</strong><br>
        <strong>Name:</strong> ${popupData?.src_name}<br>
        <strong>Phone:</strong> ${popupData?.src_phone}<br>
        <strong>Email:</strong> <a href="mailto:${popupData?.src_email}">${popupData?.src_email}</a>
      </details>
    `;
  }

  function handleClick(event) {
    if (event.features.length == 0) {
      return;
    }

    const coordinates = event.features[0].geometry.coordinates.slice();
    const properties = event.features[0].properties;

    return new Popup({maxWidth: "none"})
      .setLngLat(coordinates)
      .setHTML(popupHTML(properties))
      .addTo(map);
  }

  onMount(() => {
    map = new Map({
      container: mapContainer,
      style: "mapbox://styles/jpivarski-uchicago/cmb9rlvln014o01sdd0mk460c",
      accessToken: "pk.eyJ1IjoianBpdmFyc2tpLXVjaGljYWdvIiwiYSI6ImNtYTRsNXFvZzA4Znoyc3B0eHA4MDZrcWwifQ.Dv2YGMA3thz9A7E3OUhI9w",
      pitchWithRotate: false,
      dragRotate: false,
      bounds: [-104.5181265794389, 45.63232713888373, -96.06887947161051, 49.2702273475217],
    });

    map.addControl(new NavigationControl(), "top-left");
    map.addControl(new ScaleControl(), "bottom-left");
    map.addControl(new FullscreenControl(), "top-left");

    map.on("mouseenter", "911-addresses-7t7pj2", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "911-addresses-7t7pj2", () => {
      map.getCanvas().style.cursor = "";
    });
    map.on("click", "911-addresses-7t7pj2", handleClick);

  });

  export function flyTo(item) {
    if (map) {
      map.flyTo({ center: item.coords, zoom: item.zoom });
    }
  }
</script>

<div class="map" bind:this={mapContainer}></div>

<style>
  .map {
    position: absolute;
    width: 100%;
    height: 100%;
  }
</style>
