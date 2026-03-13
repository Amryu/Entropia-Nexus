<script>
  //@ts-nocheck
  import { loading } from "../../actions/loading";
  import Table from "./Table.svelte";

  import '$lib/style.css';

  /**
   * @typedef {Object} Props
   * @property {any} user
   * @property {any} [versions]
   * @property {any} [change]
   */

  /** @type {Props} */
  let { user, versions = [], change = null } = $props();
</script>

<style>
  a {
    text-decoration: underline;
  }
</style>

Current Change:
{#if change}
  {change.state}
  -
  <a use:loading href="{window?.location.pathname + '?mode=preview'}">View</a>
  {#if user && user.id === change.author_id}
    <a use:loading href="{window?.location.pathname + '?change=' + change.id + '&mode=edit'}">Edit</a>
  {/if}
{:else}
  None
{/if}
<br />
<br />
<Table
  header={{
    values: ['Version', 'Author', 'Date', 'View'],
    widths: ['1fr', '1fr', '1fr', '100px']
  }}
  data={
    (versions ?? []).sort((a, b) => b.number - a.number).map(version => {
      return {
        values: [
          version.number,
          version.author_name,
          version.date,
          'View'
        ],
        links: [null, null, null, window?.location.pathname + '?version=' + version.id]
      };
    })} />
