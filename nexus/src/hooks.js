export async function handleFetch({ event, request, fetch }) {
  const url = request.url;
  const ip = request.headers['x-forwarded-for'] || event.getClientAddress();

  console.log(`Fetch: '${ip}' - ${url}`);

  return await fetch(request);
}