<!--
  @component RefiningRecipesDisplay
  Read-only display for refining recipes with optional grid layout.
-->
<script>
  // @ts-nocheck
  import { getItemLink } from '$lib/util';

  

  

  

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {Array} [recipes]
   * @property {string} [materialName]
   * @property {boolean} [linkProduct]
   * @property {boolean} [linkIngredients]
   * @property {string|null} [currentEntityName]
   * @property {'list'|'grid'} [layout]
   * @property {number} [columns]
   * @property {boolean} [showEmpty]
   */

  /** @type {Props} */
  let {
    recipes = [],
    materialName = '',
    linkProduct = false,
    linkIngredients = true,
    currentEntityName = null,
    layout = 'list',
    columns = 2,
    showEmpty = false
  } = $props();

  let hasRecipes = $derived(recipes?.length > 0);
  let outputName = $derived((recipe) => materialName || recipe?.Product?.Name || 'Material');
  let outputLink = $derived((recipe) => recipe?.Product ? getItemLink(recipe.Product) : null);
  let isCurrentEntity = $derived((name) => {
    if (!name || !currentEntityName) return false;
    return name === currentEntityName;
  });
</script>

{#if hasRecipes}
  <div
    class="recipes-display"
    class:grid={layout === 'grid'}
    style={layout === 'grid' ? `--recipe-columns: ${columns};` : ''}
  >
    {#each recipes as recipe, idx}
      <div class="recipe-card">
        <div class="recipe-output-display">
          <strong class:amount-linked={linkProduct} class:amount-unlinked={!linkProduct}>
            {recipe.Amount}x
          </strong>
          {#if linkProduct && outputLink(recipe)}
            <a href={outputLink(recipe)} class="ingredient-link">{outputName(recipe)}</a>
          {:else}
            {outputName(recipe)}
          {/if}
        </div>
        {#if recipe.Ingredients?.length > 0}
          <div class="ingredients-display">
            <span class="from-label">from:</span>
            {#each recipe.Ingredients as ingredient, i}
              {#if i > 0}<span class="ingredient-separator">+</span>{/if}
              <span class="ingredient-item">
                <span
                  class="ingredient-amount"
                  class:amount-linked={linkIngredients && !isCurrentEntity(ingredient.Item?.Name)}
                  class:amount-unlinked={!linkIngredients || isCurrentEntity(ingredient.Item?.Name)}
                >
                  {ingredient.Amount}x
                </span>
                {#if linkIngredients && !isCurrentEntity(ingredient.Item?.Name) && getItemLink(ingredient.Item)}
                  <a href={getItemLink(ingredient.Item)} class="ingredient-link">{ingredient.Item?.Name || 'Unknown'}</a>
                {:else}
                  <span class="ingredient-name">{ingredient.Item?.Name || 'Unknown'}</span>
                {/if}
              </span>
            {/each}
          </div>
        {:else}
          <div class="no-ingredients">No ingredients specified</div>
        {/if}
      </div>
    {/each}
  </div>
{:else if showEmpty}
  <div class="no-recipes">No refining recipes available</div>
{/if}

<style>
  .recipes-display {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .recipes-display.grid {
    display: grid;
    grid-template-columns: repeat(var(--recipe-columns, 2), minmax(0, 1fr));
    gap: 12px;
  }

  .recipe-card {
    padding: 12px 14px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    border-left: 3px solid var(--accent-color, #4a9eff);
  }

  .recipe-output-display {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-color);
    margin-bottom: 8px;
  }

  .ingredients-display {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 6px;
    font-size: 13px;
  }

  .from-label {
    color: var(--text-muted, #999);
    margin-right: 4px;
  }

  .ingredient-separator {
    color: var(--text-muted, #999);
    margin: 0 2px;
  }

  .ingredient-item {
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
  }

  .ingredient-amount {
    font-weight: 500;
  }

  .amount-linked {
    color: var(--accent-color, #4a9eff);
  }

  .amount-unlinked {
    color: var(--text-color);
  }

  .ingredient-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .ingredient-link:hover {
    text-decoration: underline;
  }

  .ingredient-name {
    color: var(--text-color);
  }

  .no-ingredients,
  .no-recipes {
    padding: 12px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 13px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  @media (max-width: 899px) {
    .recipes-display.grid {
      grid-template-columns: 1fr;
    }
  }
</style>
