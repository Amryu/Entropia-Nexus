export async function load({ fetch }) {
  let changelog = [];
  try {
    const res = await fetch('/client/changelog.json');
    if (res.ok) changelog = await res.json();
  } catch {
    // Changelog not yet available (before first release upload)
  }
  return { changelog };
}
