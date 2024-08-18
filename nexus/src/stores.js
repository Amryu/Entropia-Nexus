import { writable } from 'svelte/store';

export const loading = writable(false);
export const darkMode = writable(true);
export const pageParams = writable({});