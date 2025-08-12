const bizSdk = require('facebook-nodejs-business-sdk');
const FacebookAdsApi = bizSdk.FacebookAdsApi;
const Page = bizSdk.Page;

// Shared helpers (copied into each function file in this template)
function corsify(body, statusCode=200) {

  return {
    statusCode,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
    },
    body: JSON.stringify(body)
  };
}

function requireAuth(event) {
  const token = process.env.ADMIN_TOKEN;
  if (!token) return; // disabled
  const hdr = (event.headers && (event.headers.authorization || event.headers.Authorization)) || "";
  const ok = hdr.startsWith("Bearer ") && hdr.slice(7) === token;
  if (!ok) { const e = new Error("Unauthorized"); e.statusCode = 401; throw e; }
}

function requireEnv(keys) {

  const missing = keys.filter(k => !process.env[k]);
  if (missing.length) {
    throw new Error("Missing environment variables: " + missing.join(", "));
  }
}


exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return corsify({ ok: true });
  try {
    requireAuth(event);
    const fbToken = (event.headers && (event.headers['x-fb-token'] || event.headers['X-FB-Token'])) || process.env.FB_ACCESS_TOKEN;
    if (!fbToken) throw new Error("Missing Facebook token (header X-FB-Token or FB_ACCESS_TOKEN).");
    const PAGE_ID = (event.queryStringParameters && event.queryStringParameters.page_id) || (JSON.parse(event.body||'{}').page_id) || process.env.PAGE_ID;
    if (!PAGE_ID) throw new Error("Missing PAGE_ID (query param or env).");
    const accessToken = fbToken;

  if (event.httpMethod === "OPTIONS") return corsify({ ok: true });
  try {
        const accessToken = (event.headers && (event.headers['x-fb-token'] || event.headers['X-FB-Token'])) || process.env.FB_ACCESS_TOKEN;
    const PAGE_ID = (event.queryStringParameters && event.queryStringParameters.page_id) || (JSON.parse(event.body||'{}').page_id) || process.env.PAGE_ID;

    FacebookAdsApi.init(accessToken);

    const postsCursor = await (new Page(PAGE_ID)).getPosts(
      ['id','message','created_time','permalink_url'],
      { limit: 25 }
    );

    const posts = postsCursor.map(p => ({ 
      id: p.id,
      short: (p.message || "").replace(/\n/g, " ").slice(0, 80),
      created: (p.created_time || "").toString().slice(0,19),
      url: p.permalink_url
    }));

    return corsify({ posts });
  } catch (err) {
    return corsify({ error: err.message || String(err) }, 500);
  }
};

