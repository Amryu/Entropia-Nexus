import { writable } from 'svelte/store';

export const loading = writable(false);
export const darkMode = writable(true);
export const pageParams = writable({});

// Server-detected initial viewport width (from User-Agent or stored cookie)
// Default to 1200 (desktop) - will be set by layout on mount
export const initialViewportWidth = writable(1200);