/** Redirect legacy /static/client/* URLs to /client/* (client <= 0.1.0 compat). */
export function GET({ params }) {
  return new Response(null, {
    status: 301,
    headers: { Location: `/client/${params.path}` },
  });
}
