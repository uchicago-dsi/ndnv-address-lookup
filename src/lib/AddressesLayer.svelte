<script>
  import { getMapContext, GeoJSON, CircleLayer, Popup } from 'svelte-maplibre';

  import { getAddressData } from '../utils/getAddressData';
  import sourceList from "../data/source-list.json";
  import copyIcon from '../assets/copy-icon.svg?raw';
  import copiedIcon from '../assets/copied-icon.svg?raw'

  const { map, loaded } = $derived(getMapContext());
  $effect(() => {
    // only load data and fill if the map is loaded and addresses is empty
    if (loaded) {
      map.getSource("addresses")?.getData().then((data) => {
        if (data.features.length == 0) {
          getAddressData().then((data) => {
            map.getSource("addresses")?.setData(data);
          });
        }
      });
    }
  });

  function mouseEnter(event) {
    event.map.getCanvas().style.cursor = "pointer";
  }
  
  function mouseLeave(event) {
    event.map.getCanvas().style.cursor = "";
  }

  let popupData = $state(null);
  let popupCopyButton = null;

  function handleClick(event) {
    let p = event.features[0].properties;
    let isMuni = p.muni != "Unincorporated"  &&  p.muni != "Undefined";
    popupData = {
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

    if (popupCopyButton !== null) {
      popupCopyButton.innerHTML = copyIcon;
    }
  }

  function handleCopy(event) {
    navigator.clipboard.writeText(popupData.addrToCopy);
    popupCopyButton.innerHTML = copiedIcon;
  }

</script>

<GeoJSON
  id="addresses"
  data={{type: "FeatureCollection", "features": []}}
  >
  <CircleLayer
    id="address-circles"
    source="addresses"
    onmouseenter={mouseEnter}
    onmouseleave={mouseLeave}
    onclick={handleClick}
    paint={{
        "circle-color": "cyan",
        "circle-stroke-width": [
          "interpolate", ["linear"], ["zoom"], 11, 0, 13, 0.5, 17, 2
        ],
        "circle-stroke-color": "black",
        "circle-radius": [
          "interpolate", ["linear"], ["zoom"], 8, 0, 13, 3, 17, 8
        ],
        "circle-stroke-opacity": {
          "base": 1,
          "stops": [[11, 0], [13, 1], [20, 1]]
        },
        "circle-opacity": {
          "base": 1,
          "stops": [[8, 0], [10, 1], [20, 1]]
        }
      }}
    beforeLayerType="symbol"
  >
    <Popup>
      <span class="popupCopyButton" bind:this={popupCopyButton} onclick={handleCopy}>{@html copyIcon}</span><br>
      <strong>Street address:</strong> {popupData?.streetAddress}<br>
      <strong>{popupData?.cityHeader}:</strong> {popupData?.city}<br>
      <strong>Zip code:</strong> {popupData?.zip}<br><br>
      <details>
        <summary><strong>Source</strong></summary>
        <strong>{popupData?.src_title}</strong><br>
        <strong>Name:</strong> {popupData?.src_name}<br>
        <strong>Phone:</strong> {popupData?.src_phone}<br>
        <strong>Email:</strong> <a href="mailto:{popupData?.src_email}">{popupData?.src_email}</a>
      </details>
    </Popup>
  </CircleLayer>
</GeoJSON>

<style>
  .popupCopyButton {
    display: inline-flex;
    justify-content: center;
    width: 100%;
  }
</style>
