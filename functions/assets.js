const bizSdk = require('facebook-nodejs-business-sdk');
const FacebookAdsApi = bizSdk.FacebookAdsApi;
const User = bizSdk.User;

function corsify(body, statusCode=200) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Content-Type, Authorization, X-FB-Token",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
    },
    body: JSON.stringify(body)
  };
}

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return corsify({ ok: true });
  try {
    const token = (event.headers && (event.headers['x-fb-token'] || event.headers['X-FB-Token']));
    if (!token) throw new Error("Missing x-fb-token header");
    FacebookAdsApi.init(token);
    const me = new User('me');
    const accounts = await me.getAdAccounts(['id','name','account_status','currency'], { limit: 50 });
    const pages = await me.getAccounts(['id','name','access_token'], { limit: 50 });
    return corsify({
      user: 'me',
      ad_accounts: accounts.map(a => ({ id: a.id, name: a.name, currency: a.currency, status: a.account_status })),
      pages: pages.map(p => ({ id: p.id, name: p.name }))
    });
  } catch (err) {
    return corsify({ error: err.message || String(err) }, 500);
  }
};
