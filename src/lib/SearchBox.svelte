<script>
  import { onMount, createEventDispatcher } from 'svelte';

  import { Input } from '@smui/textfield';
  import List, { Item, Text } from '@smui/list';
  import Menu from '@smui/menu';

  import Fuse from 'fuse.js';

  import nd_zipcodes from '../data/ND-zipcodes.json';
  import nd_places from '../data/ND-places.json';
  import nd_townships from '../data/ND-townships.json';
  import nd_counties from '../data/ND-counties.json';
  import nd_reservations from '../data/ND-reservations.json';

  const places = [...nd_zipcodes, ...nd_places, ...nd_townships, ...nd_counties, ...nd_reservations];
  const fuse = new Fuse(places, { keys: ["name"], threshold: 0.2 });

  const MAX_SEARCH_RESULTS = 10;

  let searchBox;
  let query = "";
  let results = [];
  let sayNoResultsFound = false;
  let resultsList = null;
  export let onSelect;

  function handleKeyDown(event) {
    if (event.key === "Enter"  ||  event.keyCode === 13) {
      const myresults = fuse.search(query, { limit: 1 });
      if (myresults.length != 0) {
        query = myresults[0].item.name;
        onSelect(myresults[0].item);
        resultsList.getElement().style.display = "none";
      }
      else {
        sayNoResultsFound = true;
      }
    }
  }

  function handleInput(event) {
    query = event.target.value;
    results = fuse.search(query, { limit: MAX_SEARCH_RESULTS }).map(result => result.item);
    if (resultsList !== null) {
      resultsList.getElement().style.display = "";
    }
    sayNoResultsFound = false;
  }

  // clicks outside of the whole search region should hide the matches
  onMount(() => {
    document.body.addEventListener("click", (event) => {
      if (results.length != 0  &&  searchBox !== null  &&  !searchBox.contains(event.target)) {
        resultsList.getElement().style.display = "none";
      }
      sayNoResultsFound = false;
    });
  });

  function handleSelect(result) {
    query = result.name;
    onSelect(result);
    resultsList.getElement().style.display = "none";
  }

</script>

<div bind:this={searchBox} class="search-box">
  <Input bind:value={query} oninput={handleInput} onkeydown={handleKeyDown} placeholder="Search zip code, city, county, or reservation..."/>
  <Menu class="search-results">
    {#if results.length != 0}
    <List bind:this={resultsList}>
      {#each results.slice(0, MAX_SEARCH_RESULTS) as result}
        <Item onSMUIAction={() => { handleSelect(result); }}><Text>{result.name}</Text></Item>
      {/each}
    </List>
    {:else if sayNoResultsFound}
        <Item><Text>(no results found)</Text></Item>
    {/if}
  </Menu>
</div>

<style>
:global(.search-box) {
  position: absolute;
  top: 10px;
  right: 10px;
  width: calc(100vw - 60px);
  max-width: 400px;
}

:global(.search-box input) {
  width: 100%;
  box-sizing: border-box;

  /* match the style in the Menu/List */
  font-size: 16px;
  color: rgba(0, 0, 0, 0.87);
  background-color: white;
  padding-top: 8px;
  padding-bottom: 8px;
  padding-left: 16px;
  padding-right: 16px;
}

:global(.search-results) {
  /* align with the search box */
  margin: 1px;
  margin-top: 2px;
  background: white;
}

</style>
