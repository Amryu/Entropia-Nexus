//@ts-nocheck
import { get } from 'svelte/store';
import { createPreference } from '$lib/preferences.js';

const DEFAULT_FAVOURITES = { folders: [], items: [] };

/** Persistent favourites store (localStorage + DB when logged in) */
export const favourites = createPreference('exchange.favourites', DEFAULT_FAVOURITES);

/**
 * Check if an item is in any favourites list (root or folder).
 * @param {number} itemId
 * @returns {boolean}
 */
export function isFavourite(itemId) {
  const fav = get(favourites);
  if (fav.items?.includes(itemId)) return true;
  return (fav.folders || []).some(f => f.items?.includes(itemId));
}

/**
 * Toggle an item's favourite status (add to root or remove from everywhere).
 * @param {number} itemId
 */
export function toggleFavourite(itemId) {
  if (isFavourite(itemId)) {
    removeFavourite(itemId);
  } else {
    addFavourite(itemId);
  }
}

/**
 * Add an item to favourites.
 * @param {number} itemId
 * @param {string|null} [folderId] - Optional folder ID; null = root
 */
export function addFavourite(itemId, folderId = null) {
  if (isFavourite(itemId)) return;
  favourites.update(fav => {
    const next = { ...fav, folders: [...(fav.folders || [])], items: [...(fav.items || [])] };
    if (folderId) {
      const folder = next.folders.find(f => f.id === folderId);
      if (folder) {
        folder.items = [...(folder.items || []), itemId];
      } else {
        next.items.push(itemId);
      }
    } else {
      next.items.push(itemId);
    }
    return next;
  });
}

/**
 * Remove an item from all favourites (root and all folders).
 * @param {number} itemId
 */
export function removeFavourite(itemId) {
  favourites.update(fav => {
    const next = {
      ...fav,
      items: (fav.items || []).filter(id => id !== itemId),
      folders: (fav.folders || []).map(f => ({
        ...f,
        items: (f.items || []).filter(id => id !== itemId)
      }))
    };
    return next;
  });
}

/**
 * Create a new folder.
 * @param {string} name
 * @returns {string} The new folder's ID
 */
export function createFolder(name) {
  const id = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36);
  favourites.update(fav => {
    const folders = [...(fav.folders || [])];
    folders.push({
      id,
      name: name || 'New Folder',
      items: [],
      order: folders.length
    });
    return { ...fav, folders };
  });
  return id;
}

/**
 * Rename a folder.
 * @param {string} folderId
 * @param {string} name
 */
export function renameFolder(folderId, name) {
  favourites.update(fav => ({
    ...fav,
    folders: (fav.folders || []).map(f =>
      f.id === folderId ? { ...f, name } : f
    )
  }));
}

/**
 * Delete a folder. Items in the folder are moved to root by default.
 * @param {string} folderId
 * @param {boolean} [keepItems=true] - If true, items move to root; if false, items are removed
 */
export function deleteFolder(folderId, keepItems = true) {
  favourites.update(fav => {
    const folder = (fav.folders || []).find(f => f.id === folderId);
    const movedItems = keepItems && folder ? (folder.items || []) : [];
    return {
      ...fav,
      items: [...(fav.items || []), ...movedItems],
      folders: (fav.folders || []).filter(f => f.id !== folderId)
    };
  });
}

/**
 * Move an item to a folder (or to root if folderId is null).
 * Removes from current location first.
 * @param {number} itemId
 * @param {string|null} folderId - Target folder ID, or null for root
 */
export function moveToFolder(itemId, folderId) {
  favourites.update(fav => {
    // Remove from everywhere first
    const next = {
      ...fav,
      items: (fav.items || []).filter(id => id !== itemId),
      folders: (fav.folders || []).map(f => ({
        ...f,
        items: (f.items || []).filter(id => id !== itemId)
      }))
    };
    // Add to target
    if (folderId) {
      const folder = next.folders.find(f => f.id === folderId);
      if (folder) {
        folder.items = [...(folder.items || []), itemId];
      } else {
        next.items.push(itemId);
      }
    } else {
      next.items.push(itemId);
    }
    return next;
  });
}

/**
 * Reorder folders by providing an ordered array of folder IDs.
 * @param {string[]} orderedIds
 */
export function reorderFolders(orderedIds) {
  favourites.update(fav => {
    const folderMap = {};
    for (const f of (fav.folders || [])) folderMap[f.id] = f;
    const reordered = orderedIds
      .filter(id => folderMap[id])
      .map((id, i) => ({ ...folderMap[id], order: i }));
    // Append any folders not in orderedIds
    for (const f of (fav.folders || [])) {
      if (!orderedIds.includes(f.id)) {
        reordered.push({ ...f, order: reordered.length });
      }
    }
    return { ...fav, folders: reordered };
  });
}
