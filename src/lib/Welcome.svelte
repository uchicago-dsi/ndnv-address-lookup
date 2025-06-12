<script>
  import { writable } from 'svelte/store';

  import Dialog from '@smui/dialog';
  import { Content, InitialFocus } from '@smui/dialog';
  import Button from '@smui/button';

  let isOpen = $state(true);
  let okayButton;

  const showWelcome = (localStorage.getItem("showWelcome") || "yes") == "yes";

</script>

{#if showWelcome}
  <Dialog open={isOpen}>
    <Content>
      <img class="logo" src="/ndnv-logo.svg">

      <h2>Find your address!</h2>

      <p>Use the search box, zoom in, or click the <img src="data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='29' height='29' fill='%23333' viewBox='0 0 20 20'%3E%3Cpath d='M10 4C9 4 9 5 9 5v.1A5 5 0 0 0 5.1 9H5s-1 0-1 1 1 1 1 1h.1A5 5 0 0 0 9 14.9v.1s0 1 1 1 1-1 1-1v-.1a5 5 0 0 0 3.9-3.9h.1s1 0 1-1-1-1-1-1h-.1A5 5 0 0 0 11 5.1V5s0-1-1-1m0 2.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 1 1 0-7'/%3E%3Ccircle cx='10' cy='10' r='2'/%3E%3C/svg%3E" style="margin-bottom: -0.5em;"> button to find your current location. Then, click on a dot <img src="data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='29' height='29' fill='%23333' viewBox='0 0 20 20'%3E%3Ccircle cx='10' cy='10' r='5' style='fill: %235ef2de; stroke: black;'/%3E%3C/svg%3E" style="margin-bottom: -0.5em;"> to get the building's full address, with street number.</p>

      <p>All addresses are from North Dakota's <a target="_blank" href="https://gishubdata-ndgov.hub.arcgis.com/datasets/NDGOV::ndgishub-site-structure-address-points/about">Next Generation 911 address dataset</a>, hosted on <a target="_blank" href="https://gishubdata-ndgov.hub.arcgis.com/">North Dakota GIS Hub</a>.</p>

      <input
        type="checkbox"
        id="noshow"
        name="noshow"
        value="noshow"
        onchange={(event) => { localStorage.setItem("showWelcome", event.target.checked ? "no" : "yes"); }}
      /> <label for="noshow">Don't show this again</label>

      <Button class="okay" use={[InitialFocus]} onclick={() => {isOpen = false;}}>Okay!</Button>
    </Content>
  </Dialog>
{/if}

<style>
  img.logo {
    display: block;
    margin-left: auto;
    margin-right: auto;
    margin-bottom: 20px;
    width: 50%;
    max-width: 400px;
  }

  :global(.okay) {
    display: block;
    margin-left: auto;
    margin-right: auto;
    margin-top: 20px;
    border: 1px solid #808080;
    background: #f0f0f0;
    color: black;
    font-weight: bold;
  }
</style>
