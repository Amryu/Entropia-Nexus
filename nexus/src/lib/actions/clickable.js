/**
 * Svelte action that makes a non-interactive element (div, span) accessible as a button.
 * Adds role="button", tabindex="0", and Enter/Space keyboard handling.
 *
 * Usage: <div use:clickable on:click={handler}>
 * With tabindex override: <div use:clickable={{ tabindex: -1 }} on:click={handler}>
 */
export function clickable(node, options = {}) {
  const tabindex = options?.tabindex ?? 0;

  if (!node.hasAttribute('role')) {
    node.setAttribute('role', 'button');
  }
  if (!node.hasAttribute('tabindex')) {
    node.setAttribute('tabindex', String(tabindex));
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      node.click();
    }
  }

  node.addEventListener('keydown', handleKeydown);

  return {
    update(newOptions) {
      node.setAttribute('tabindex', String(newOptions?.tabindex ?? 0));
    },
    destroy() {
      node.removeEventListener('keydown', handleKeydown);
    }
  };
}
