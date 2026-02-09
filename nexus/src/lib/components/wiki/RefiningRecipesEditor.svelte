<!--
  @component RefiningRecipesEditor
  Editor for material RefiningRecipes arrays.
  Each recipe has Amount (product count) and Ingredients (array of Item + Amount).
-->
<script>
  // @ts-nocheck
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';
  import SearchInput from './SearchInput.svelte';
  import RefiningRecipesDisplay from './RefiningRecipesDisplay.svelte';

  /** @type {Array} RefiningRecipes array */
  export let recipes = [];

  /** @type {string} Field path for updateField */
  export let fieldName = 'RefiningRecipes';

  /** @type {string} The material name (for display) */
  export let materialName = '';

  // Show section if has recipes or in edit mode
  $: shouldShow = $editMode || (recipes?.length > 0);

  // === Recipe CRUD Operations ===
  function addRecipe() {
    const newRecipe = {
      Amount: 1,
      Ingredients: []
    };
    updateField(fieldName, [...recipes, newRecipe]);
  }

  function updateRecipeAmount(recipeIndex, amount) {
    const newRecipes = [...recipes];
    newRecipes[recipeIndex] = {
      ...newRecipes[recipeIndex],
      Amount: amount
    };
    updateField(fieldName, newRecipes);
  }

  function removeRecipe(recipeIndex) {
    updateField(fieldName, recipes.filter((_, i) => i !== recipeIndex));
  }

  // === Ingredient CRUD Operations ===
  function addIngredient(recipeIndex) {
    const newRecipes = [...recipes];
    const newIngredient = {
      Item: { Name: '' },
      Amount: 1
    };
    newRecipes[recipeIndex] = {
      ...newRecipes[recipeIndex],
      Ingredients: [...(newRecipes[recipeIndex].Ingredients || []), newIngredient]
    };
    updateField(fieldName, newRecipes);
  }

  function updateIngredient(recipeIndex, ingredientIndex, field, value) {
    const newRecipes = [...recipes];
    const newIngredients = [...newRecipes[recipeIndex].Ingredients];

    if (field === 'Name') {
      newIngredients[ingredientIndex] = {
        ...newIngredients[ingredientIndex],
        Item: { Name: value }
      };
    } else if (field === 'Amount') {
      newIngredients[ingredientIndex] = {
        ...newIngredients[ingredientIndex],
        Amount: value
      };
    }

    newRecipes[recipeIndex] = {
      ...newRecipes[recipeIndex],
      Ingredients: newIngredients
    };
    updateField(fieldName, newRecipes);
  }

  function removeIngredient(recipeIndex, ingredientIndex) {
    const newRecipes = [...recipes];
    newRecipes[recipeIndex] = {
      ...newRecipes[recipeIndex],
      Ingredients: newRecipes[recipeIndex].Ingredients.filter((_, i) => i !== ingredientIndex)
    };
    updateField(fieldName, newRecipes);
  }
</script>

{#if shouldShow}
  <div class="refining-recipes-editor" class:editing={$editMode}>
    {#if $editMode}
      <div class="recipes-edit-list">
        {#each recipes as recipe, recipeIdx}
          <div class="recipe-edit-card">
            <div class="recipe-header">
              <div class="recipe-output">
                <span class="output-label">Produces</span>
                <input
                  type="number"
                  class="amount-input"
                  value={recipe.Amount ?? 1}
                  step="1"
                  min="1"
                  on:change={(e) => updateRecipeAmount(recipeIdx, parseInt(e.target.value) || 1)}
                />
                <span class="output-name">x {materialName || 'Material'}</span>
              </div>
              <button class="btn-remove-recipe" on:click={() => removeRecipe(recipeIdx)} title="Remove recipe">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div class="ingredients-section">
              <div class="ingredients-label">Ingredients:</div>
              {#each recipe.Ingredients || [] as ingredient, ingIdx}
                <div class="ingredient-row">
                  <SearchInput
                    value={ingredient.Item?.Name || ''}
                    placeholder="Search item..."
                    apiEndpoint="/search/items"
                    displayFn={(item) => item?.Name || ''}
                    on:change={(e) => updateIngredient(recipeIdx, ingIdx, 'Name', e.detail.value)}
                    on:select={(e) => updateIngredient(recipeIdx, ingIdx, 'Name', e.detail.value)}
                  />
                  <span class="ingredient-x">×</span>
                  <input
                    type="number"
                    class="amount-input small"
                    value={ingredient.Amount ?? 1}
                    step="1"
                    min="1"
                    on:change={(e) => updateIngredient(recipeIdx, ingIdx, 'Amount', parseInt(e.target.value) || 1)}
                  />
                  <button class="btn-remove-small" on:click={() => removeIngredient(recipeIdx, ingIdx)} title="Remove ingredient">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>
              {/each}
              <button class="btn-add-ingredient" on:click={() => addIngredient(recipeIdx)}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                Add Ingredient
              </button>
            </div>
          </div>
        {/each}
        <button class="btn-add-recipe" on:click={addRecipe}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Recipe
        </button>
      </div>
    {:else}
      <RefiningRecipesDisplay
        recipes={recipes}
        {materialName}
        showEmpty={true}
      />
    {/if}
  </div>
{/if}

<style>
  .refining-recipes-editor {
    width: 100%;
  }

  /* Edit mode styles */
  .recipes-edit-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .recipe-edit-card {
    padding: 14px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 8px;
    border-left: 3px solid var(--accent-color, #4a9eff);
  }

  .recipe-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .recipe-output {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .output-label {
    font-size: 12px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
  }

  .output-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-color);
  }

  .amount-input {
    width: 60px;
    padding: 5px 6px;
    font-size: 13px;
    text-align: left;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .amount-input.small {
    width: 50px;
  }

  .ingredients-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .ingredients-label {
    font-size: 12px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    margin-bottom: 4px;
  }

  .ingredient-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    background-color: var(--secondary-color);
    border-radius: 4px;
  }

  .ingredient-row :global(.item-search) {
    flex: 1;
    min-width: 150px;
  }

  .ingredient-x {
    color: var(--text-muted, #999);
    font-size: 14px;
  }

  .btn-remove-recipe {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--error-color, #ff6b6b);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-remove-recipe:hover {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-remove-small {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0;
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--error-color, #ff6b6b);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-remove-small:hover {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-add-ingredient {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
    width: fit-content;
  }

  .btn-add-ingredient:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }

  .btn-add-recipe {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 12px 16px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 6px;
    color: var(--text-muted, #999);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-add-recipe:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .ingredient-row {
      flex-wrap: wrap;
    }

    .ingredient-row :global(.item-search) {
      flex: 1 1 100%;
      order: 1;
    }

    .ingredient-x {
      order: 2;
    }

    .amount-input.small {
      order: 3;
    }

    .btn-remove-small {
      order: 4;
      margin-left: auto;
    }
  }
</style>
