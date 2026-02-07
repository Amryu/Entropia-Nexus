// @ts-nocheck

export async function load({ params, fetch, parent }) {
  const parentData = await parent();

  // Load guide tree for sidebar navigation
  const treeRes = await fetch('/api/guides');
  const treeData = treeRes.ok ? await treeRes.json() : [];
  const tree = Array.isArray(treeData) ? treeData : [];

  let lesson = null;
  let paragraphs = [];
  let lessonApiPath = '';

  if (params.slug) {
    // Find the lesson in the tree to get its IDs for the API call
    for (const cat of tree) {
      for (const ch of cat.chapters || []) {
        const found = (ch.lessons || []).find(l => l.slug === params.slug);
        if (found) {
          lessonApiPath = `/api/guides/${cat.id}/chapters/${ch.id}/lessons/${found.id}`;
          const lessonRes = await fetch(lessonApiPath);
          if (lessonRes.ok) {
            const data = await lessonRes.json();
            paragraphs = data.paragraphs || [];
            lesson = data;
          }
          break;
        }
      }
      if (lesson) break;
    }
  }

  return {
    tree,
    lesson,
    paragraphs,
    slug: params.slug,
    lessonApiPath,
    session: parentData.session
  };
}
