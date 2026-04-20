-- Migration 134: Strip the leading <h2>...</h2> from every Fishing-guide
-- paragraph.
--
-- The lesson page already renders the lesson title as <h1 class="lesson-title">
-- (see information/guides/[[slug]]/+page.svelte), so the seed migration's
-- per-paragraph <h2> headings duplicated the title on screen. This patches the
-- already-applied data on prod; migration 133 has been updated in the same
-- commit so fresh installs don't reintroduce the issue.

BEGIN;

UPDATE guide_paragraphs gp
   SET content_html = regexp_replace(gp.content_html, '^\s*<h2>[^<]*</h2>\s*\n?', '', 'i'),
       updated_at   = now()
  FROM guide_lessons l
 WHERE gp.lesson_id = l.id
   AND l.slug LIKE 'fishing-%'
   AND gp.content_html ~* '^\s*<h2>[^<]*</h2>';

COMMIT;
