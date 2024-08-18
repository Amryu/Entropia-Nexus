import path from 'path';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig(({ mode }) => ({
	plugins: [sveltekit()],
	build: {
		sourcemap: mode === 'development'
	},
	preview: {
		port: 5173
	},
	resolve: {
		alias: {
			$common: path.resolve('../common'),
		}
	}
}));
