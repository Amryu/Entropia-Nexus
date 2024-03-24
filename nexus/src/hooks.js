export async function handleFetch({ event, request, fetch }) {
  const url = request.url;
  const ip = request.headers['x-forwarded-for'] || event.getClientAddress();

  return await fetch(request);
}