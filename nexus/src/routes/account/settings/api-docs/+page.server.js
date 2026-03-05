// @ts-nocheck
import { requireVerified } from '$lib/server/auth.js';
import MarkdownIt from 'markdown-it';
import apiDocsRaw from '$lib/data/api-docs.md?raw';

function slugify(text) {
  return text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').trim();
}

const md = new MarkdownIt({ html: false, linkify: true });

const headings = [];
const seen = new Set();

const defaultOpen = md.renderer.rules.heading_open;
const defaultClose = md.renderer.rules.heading_close;

const downloadBtn = `<a href="/account/settings/api-docs/raw" download="entropia-nexus-api-docs.md" class="download-btn" title="Download as Markdown (for AI agents)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>Download Markdown</a>`;

md.renderer.rules.heading_open = (tokens, idx, options, env, self) => {
  const level = parseInt(tokens[idx].tag.slice(1));
  if (level === 1) {
    return `<div class="h1-row"><h1>`;
  }
  if (level === 2 || level === 3) {
    const inline = tokens[idx + 1];
    const text = inline?.children?.map(t => t.content).join('') || '';
    let id = slugify(text);
    if (seen.has(id)) {
      let n = 2;
      while (seen.has(`${id}-${n}`)) n++;
      id = `${id}-${n}`;
    }
    seen.add(id);
    headings.push({ id, text, level });
    return `<${tokens[idx].tag} id="${id}">`;
  }
  return defaultOpen ? defaultOpen(tokens, idx, options, env, self) : self.renderToken(tokens, idx, options);
};

md.renderer.rules.heading_close = (tokens, idx, options, env, self) => {
  const level = parseInt(tokens[idx].tag.slice(1));
  if (level === 1) {
    return `</h1>${downloadBtn}</div>`;
  }
  return defaultClose ? defaultClose(tokens, idx, options, env, self) : self.renderToken(tokens, idx, options);
};

const html = md.render(apiDocsRaw);

export async function load({ locals }) {
  requireVerified(locals);
  return { html, headings };
}
