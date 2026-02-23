// @ts-nocheck
import { requireVerified } from '$lib/server/auth.js';
import MarkdownIt from 'markdown-it';
import apiDocsRaw from '$lib/data/api-docs.md?raw';

const md = new MarkdownIt({ html: false, linkify: true });
const html = md.render(apiDocsRaw);

export async function load({ locals }) {
  requireVerified(locals);
  return { html };
}
