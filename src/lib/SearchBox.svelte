<script>
  import { onMount, createEventDispatcher } from 'svelte';

  import { Input } from '@smui/textfield';
  import List, { Item, Text } from '@smui/list';
  import Menu from '@smui/menu';

  import Fuse from 'fuse.js';

  import nd_zipcodes from '../data/ND-zipcodes.json';
  import nd_places from '../data/ND-places.json';

  const places = [...nd_zipcodes, ...nd_places];
  const fuse = new Fuse(places, { keys: ["name"] });

  let searchBox;
  let query = "";
  let results = [];
  export let onSelect;

  function handleKeyDown(event) {
    if (event.key === "Enter"  ||  event.keyCode === 13) {
      const myresults = fuse.search(query);
      if (myresults.length != 0) {
        query = myresults[0].item.name;
        results = [];
        onSelect(myresults[0].item);
      }
    }
  }

  function handleInput(event) {
    query = event.target.value;
    results = fuse.search(query).map(result => result.item);
  }

  // clicks outside of the whole search region should hide the matches
  onMount(() => {
    document.body.addEventListener("click", (event) => {
      if (results.length != 0  &&  searchBox !== null  &&  !searchBox.contains(event.target)) {
        results = [];
      }
    });
  });

</script>

<div bind:this={searchBox} class="search-box">
  <Input bind:value={query} oninput={handleInput} onkeydown={handleKeyDown} placeholder="Search for city or zip code..." />
  <Menu class="search-results">
    {#if results.length != 0}
    <List>
      {#each results.slice(0, 5) as result}
        <Item onSMUIAction={() => {results = []; onSelect(result);}}><Text>{result.name}</Text></Item>
      {/each}
    </List>
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
