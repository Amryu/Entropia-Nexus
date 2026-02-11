import { writable } from 'svelte/store';

let nextId = 0;

/** @type {import('svelte/store').Writable<Array<{id: number, message: string, type: string, duration: number}>>} */
export const toasts = writable([]);

/**
 * Show a toast message.
 * @param {string} message
 * @param {{ type?: 'error'|'warning'|'success'|'info', duration?: number }} [opts]
 */
export function addToast(message, opts = {}) {
  const id = nextId++;
  const type = opts.type ?? 'error';
  const duration = opts.duration ?? 6000;

  toasts.update(t => [...t, { id, message, type, duration }]);

  if (duration > 0) {
    setTimeout(() => removeToast(id), duration);
  }
}

/** @param {number} id */
export function removeToast(id) {
  toasts.update(t => t.filter(x => x.id !== id));
}
