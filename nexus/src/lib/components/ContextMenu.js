import { tick } from 'svelte';

export function contextmenu(node, { contextMenu, payload }) {
  let contextMenuFunc = (e) => showContextMenu(e, contextMenu, payload);

  node.addEventListener('contextmenu', contextMenuFunc);

  return {
    destroy() {
      node.removeEventListener('contextmenu', contextMenuFunc);
    }
  };
}

async function showContextMenu(event, contextMenu, payload) {
  event.preventDefault();
  contextMenu.contextMenuPos = { x: event.clientX, y: event.clientY };
  contextMenu.visible = true;
  contextMenu.payload = payload;

  await tick();

  const contextMenuHeight = contextMenu.element.offsetHeight;

  // Check if the context menu fits in the down direction
  if (contextMenu.contextMenuPos.y + contextMenuHeight > window.innerHeight) {
    // If it doesn't fit, display it upwards
    contextMenu.contextMenuPos.y -= contextMenuHeight;
  }
}