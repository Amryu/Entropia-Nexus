// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			session?: {
				userId?: string;
				[key: string]: unknown;
			};
		}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}

	interface Window {
		turnstile?: {
			render(container: HTMLElement, options: Record<string, unknown>): string;
			reset(widgetId: string): void;
			remove(widgetId: string): void;
		};
		clipboardData?: DataTransfer;
	}
}

export {};
