//@ts-nocheck
import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';

const LS_PREFIX = 'nexus.pref.';

// Active debounce timers keyed by preference key
const debounceTimers = {};

/**
 * Create a preference store that abstracts localStorage vs DB persistence.
 *
 * - When not logged in: reads/writes localStorage only.
 * - When logged in: reads from DB (authoritative), writes to both localStorage + DB.
 * - On first load when logged in: if DB has no entry but localStorage does, migrates up.
 *
 * @param {string} key - The preference key (e.g., 'exchange.favourites')
 * @param {*} defaultValue - Default value if nothing is stored
 * @param {{ debounceMs?: number }} [options] - Options (debounceMs for frequent writes)
 * @returns {import('svelte/store').Writable & { load: (userId?: string|null) => Promise<void> }}
 */
export function createPreference(key, defaultValue, options = {}) {
  const { debounceMs = 0 } = options;
  const store = writable(defaultValue);
  let currentUserId = null;
  let loaded = false;

  // --- localStorage helpers ---

  function readFromLocalStorage() {
    if (!browser) return null;
    try {
      const raw = localStorage.getItem(LS_PREFIX + key);
      return raw != null ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function writeToLocalStorage(value) {
    if (!browser) return;
    try {
      localStorage.setItem(LS_PREFIX + key, JSON.stringify(value));
    } catch (e) {
      console.warn(`[preferences] Failed to write '${key}' to localStorage:`, e);
    }
  }

  // --- DB helpers ---

  async function readFromDB() {
    try {
      const res = await fetch(`/api/users/preferences/${encodeURIComponent(key)}`);
      if (res.ok) {
        const result = await res.json();
        return result?.data ?? null;
      }
    } catch {}
    return null;
  }

  async function writeToDB(value) {
    try {
      await fetch('/api/users/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, data: value }),
      });
    } catch (e) {
      console.warn(`[preferences] Failed to write '${key}' to DB:`, e);
    }
  }

  function scheduleDBWrite(value) {
    if (!currentUserId) return;
    if (debounceMs > 0) {
      clearTimeout(debounceTimers[key]);
      debounceTimers[key] = setTimeout(() => writeToDB(value), debounceMs);
    } else {
      writeToDB(value); // fire-and-forget
    }
  }

  // --- Store method overrides ---

  const originalSet = store.set;
  const originalUpdate = store.update;

  store.set = (value) => {
    originalSet(value);
    writeToLocalStorage(value);
    scheduleDBWrite(value);
  };

  store.update = (fn) => {
    originalUpdate((current) => {
      const next = fn(current);
      writeToLocalStorage(next);
      scheduleDBWrite(next);
      return next;
    });
  };

  /**
   * Load the preference value.
   * Reads from localStorage immediately, then from DB if userId is provided.
   * Handles migration from localStorage → DB when DB is empty.
   *
   * @param {string|null} [userId] - User ID if logged in
   */
  store.load = async (userId = null) => {
    currentUserId = userId;

    // Read from localStorage first (instant)
    const localValue = readFromLocalStorage();
    if (localValue != null) {
      originalSet(localValue);
    }

    // If logged in, check DB
    if (userId) {
      const dbValue = await readFromDB();
      if (dbValue != null) {
        // DB is authoritative — use its value
        originalSet(dbValue);
        writeToLocalStorage(dbValue); // keep localStorage in sync
      } else if (localValue != null) {
        // DB has nothing but localStorage does — migrate upward
        await writeToDB(localValue);
      }
    }

    loaded = true;
  };

  return store;
}
