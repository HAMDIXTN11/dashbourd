const bizSdk = require('facebook-nodejs-business-sdk');
const FacebookAdsApi = bizSdk.FacebookAdsApi;
const AdAccount = bizSdk.AdAccount;
const Campaign = bizSdk.Campaign;
const AdSet = bizSdk.AdSet;

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


function minorOffsetForCurrency(cur) {
  const three = new Set(["BHD","JOD","KWD","OMR","TND","IQD"]);
  return three.has(cur.toUpperCase()) ? 1000 : 100;
}

function minorToTnd(x, offset) { return x / offset; }
function tndToMinor(x, offset) { return Math.round(x * offset); }

async function findCampaignIdByName(name, adAccountId) {
  const acc = new AdAccount(adAccountId);
  const camps = await acc.getCampaigns(['id','name'], { effective_status: ['ACTIVE','PAUSED'] });
  const found = camps.find(c => c.name === name);
  if (!found) throw new Error(`Campaign not found: ${name}`);
  return found.id;
}

async function findAdSetIdByName(name, campaignId) {
  const sets = await (new Campaign(campaignId)).getAdSets(['id','name'], { effective_status: ['ACTIVE','PAUSED'] });
  const found = sets.find(s => s.name === name);
  if (!found) throw new Error(`AdSet not found: ${name}`);
  return found.id;
}

async function insightsYesterdayForAdSet(adsetId) {
  const fields = ['spend','actions'];
  const since = new Date(Date.now()-86400000).toISOString().slice(0,10);
  const params = { time_range: { since, until: since } };
  const data = await (new AdSet(adsetId)).getInsights(fields, params);
  return data && data[0] ? data[0] : {};
}

function sumActions(actions, keys) {
  if (!Array.isArray(actions)) return 0;
  let t=0;
  for (const a of actions) {
    if (keys.has(a.action_type)) {
      const v = Number(a.value || 0);
      if (!Number.isNaN(v)) t += v;
    }
  }
  return t;
}

async function adjustBudget(adsetId, offset, target, mode, minTnd, maxTnd) {
  const info = await (new AdSet(adsetId)).get([ 'daily_budget' ]);
  const currMinor = Number(info.daily_budget || 0);
  const currTnd = minorToTnd(currMinor, offset);

  const ins = await insightsYesterdayForAdSet(adsetId);
  const spend = Number(ins.spend || 0);
  const actions = ins.actions || [];

  const keys = mode === 'messages'
    ? new Set(['messaging_conversation_started','onsite_conversion.messaging_first_reply','onsite_conversion.messaging_conversation_started_7d','omni_conversation','whatsapp_conversation_started'])
    : new Set(['post_engagement','onsite_conversion.post_save','post_reaction']);

  const qty = sumActions(actions, keys);
  const kpi = qty > 0 ? (spend / qty) : null;

  let newBudget = currTnd;
  if (kpi === null) newBudget = Math.max(minTnd, currTnd * 0.9);
  else if (kpi <= target) newBudget = Math.min(maxTnd, currTnd * 1.20);
  else if (kpi > target * 1.2) newBudget = Math.max(minTnd, currTnd * 0.80);

  if (Math.abs(newBudget - currTnd) >= 0.5) {
    await (new AdSet(adsetId)).update({ daily_budget: tndToMinor(newBudget, offset) });
  }

  return { spend, qty, kpi, old_budget: currTnd, new_budget: newBudget };
}

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return corsify({ ok: true });
  try {
    requireAuth(event);
    const fbToken = (event.headers && (event.headers['x-fb-token'] || event.headers['X-FB-Token'])) || process.env.FB_ACCESS_TOKEN;
    if (!fbToken) throw new Error("Missing Facebook token (header X-FB-Token or FB_ACCESS_TOKEN).");
    const body = JSON.parse(event.body || "{}");
    const adAccountId = (event.queryStringParameters && event.queryStringParameters.ad_account_id) || body.ad_account_id || process.env.AD_ACCOUNT_ID;
    if (!adAccountId) throw new Error("Missing ad_account_id (body or env AD_ACCOUNT_ID).");
    const accessToken = fbToken;

  if (event.httpMethod === "OPTIONS") return corsify({ ok: true });
  try {
        const accessToken = (event.headers && (event.headers['x-fb-token'] || event.headers['X-FB-Token'])) || process.env.FB_ACCESS_TOKEN;
    const adAccountId = (event.queryStringParameters && event.queryStringParameters.ad_account_id) || (JSON.parse(event.body||'{}').ad_account_id) || process.env.AD_ACCOUNT_ID;
    FacebookAdsApi.init(accessToken);

    const body = JSON.parse(event.body || "{}");

    const msgTarget = Number(body.msg_target_cpa || 2.5);
    const msgMin = Number(body.msg_min || 10);
    const msgMax = Number(body.msg_max || 200);

    const engTarget = Number(body.eng_target_cpe || 0.2);
    const engMin = Number(body.eng_min || 10);
    const engMax = Number(body.eng_max || 150);

    const accInfo = await (new AdAccount(adAccountId)).get([ "currency" ]);
    const offset = minorOffsetForCurrency(accInfo.currency || "TND");

    const msgCampName = `${(JSON.parse(event.body||'{}').brand) || process.env.BRAND || 'Corella Store'} | CTWA | Sales`;
    const engCampName = `${(JSON.parse(event.body||'{}').brand) || process.env.BRAND || 'Corella Store'} | Engagement`;
    const msgAdsetName = "TN | 18-45 | FB+IG | Messages";
    const engAdsetName = "TN | 18-45 | FB+IG | Boost";

    const msgCampId = await findCampaignIdByName(msgCampName, adAccountId);
    const engCampId = await findCampaignIdByName(engCampName, adAccountId);
    const msgAdsetId = await findAdSetIdByName(msgAdsetName, msgCampId);
    const engAdsetId = await findAdSetIdByName(engAdsetName, engCampId);

    const msgRes = await adjustBudget(msgAdsetId, offset, msgTarget, 'messages', msgMin, msgMax);
    const engRes = await adjustBudget(engAdsetId, offset, engTarget, 'engagement', engMin, engMax);

    return corsify({
      ok: true,
      messages: msgRes,
      engagement: engRes
    });
  } catch (err) {
    return corsify({ error: err.message || String(err) }, 500);
  }
};

