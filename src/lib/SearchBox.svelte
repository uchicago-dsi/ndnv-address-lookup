<script>
  import { onMount, createEventDispatcher } from 'svelte';

  import { Input } from '@smui/textfield';
  import List, { Item, Text } from '@smui/list';
  import Menu from '@smui/menu';

  import Fuse from 'fuse.js';

  const places = [
    { name: "Fort Yates", coords: [-100.63404003758103, 46.089099445920105], zoom: 15 },
    { name: "Fott Totten", coords: [-98.99062524672397, 47.977573309592515], zoom: 15 },
  ];
  const fuse = new Fuse(places, { keys: ["name"] });

  let searchBox;
  let query = "";
  let results = [];
  export let onSelect;

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
  <Input bind:value={query} oninput={handleInput} placeholder="Search..." />
  <Menu class="search-results">
    {#if results.length != 0}
    <List>
      {#each results.slice(0, 5) as result}
        <Item onSMUIAction={() => {onSelect(result);}}><Text>{result.name}</Text></Item>
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
  width: 400px;
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
