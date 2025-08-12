const bizSdk = require('facebook-nodejs-business-sdk');
const FacebookAdsApi = bizSdk.FacebookAdsApi;
const AdAccount = bizSdk.AdAccount;
const Campaign = bizSdk.Campaign;
const AdSet = bizSdk.AdSet;
const AdCreative = bizSdk.AdCreative;
const Ad = bizSdk.Ad;

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

function tndToMinor(x, offset) { return Math.round(x * offset); }

async function ensureCampaign(name, objective, adAccountId) {
  const acc = new AdAccount(adAccountId);
  const camps = await acc.getCampaigns(['id','name'], { effective_status: ['ACTIVE','PAUSED'] });
  const found = camps.find(c => c.name === name);
  if (found) return found.id;
  const camp = await acc.createCampaign({
    name, objective, status: 'PAUSED', buying_type: 'AUCTION', special_ad_categories: []
  });
  return camp.id;
}

async function ensureAdSet(name, campaignId, dailyMinor, optimization_goal) {
  const sets = await (new Campaign(campaignId)).getAdSets(['id','name','campaign_id'], { effective_status: ['ACTIVE','PAUSED'] });
  const found = sets.find(s => s.name === name);
  if (found) {
    await (new AdSet(found.id)).update({ daily_budget: dailyMinor });
    return found.id;
  }
  const adset = await (new AdAccount(AD_ACCOUNT_ID)).createAdSet({
    name,
    campaign_id: campaignId,
    daily_budget: dailyMinor,
    billing_event: 'IMPRESSIONS',
    optimization_goal,
    bid_strategy: 'LOWEST_COST_WITHOUT_CAP',
    status: 'PAUSED',
    promoted_object: { page_id: PAGE_ID },
    targeting: {
      age_min: 18, age_max: 45,
      geo_locations: { countries: ['TN'] },
      publisher_platforms: ['facebook','instagram'],
      facebook_positions: ['feed','marketplace','video_feeds','stories','reels'],
      instagram_positions: ['stream','story','reels']
    }
  });
  return adset.id;
}

async function createEngagementAds(adsetId, pagePostIds) {
  const AD_ACCOUNT_ID = (event.queryStringParameters && event.queryStringParameters.ad_account_id) || (JSON.parse(event.body||'{}').ad_account_id) || AD_ACCOUNT_ID;
  const acc = new AdAccount(AD_ACCOUNT_ID);
  const adIds = [];
  for (let i=0;i<pagePostIds.length;i++) {
    const ppid = pagePostIds[i];
    const cr = await acc.createAdCreative({
      name: `Boost | Post ${i+1}`,
      object_story_id: ppid
    });
    const ad = await acc.createAd({
      name: `Boost | Post ${i+1}`,
      adset_id: adsetId,
      creative: { creative_id: cr.id },
      status: 'PAUSED'
    });
    adIds.push(ad.id);
  }
  return adIds;
}

async function ensureMsgCreative() {
  const AD_ACCOUNT_ID = (event.queryStringParameters && event.queryStringParameters.ad_account_id) || (JSON.parse(event.body||'{}').ad_account_id) || AD_ACCOUNT_ID;
  const acc = new AdAccount(AD_ACCOUNT_ID);
  const wanted = "CTWA | Hero Creative";
  const list = await acc.getAdCreatives(['id','name'], { limit: 100 });
  const found = list.find(c => c.name === wanted);
  if (found) return found.id;
  const creative = await acc.createAdCreative({
    name: wanted,
    object_story_spec: {
      page_id: PAGE_ID,
      link_data: {
        link: `https://wa.me/${(JSON.parse(event.body||'{}').whatsapp_number) || WHATSAPP}`,
        message: "Corella Store – كلمنا على واتساب باش نحجزولك العرض والمقاس 👇",
        call_to_action: {
          type: "WHATSAPP_MESSAGE",
          value: { link: `https://wa.me/${(JSON.parse(event.body||'{}').whatsapp_number) || WHATSAPP}` }
        }
      }
    }
  });
  return creative.id;
}

async function ensureMsgAd(adsetId, creativeId) {
  const AD_ACCOUNT_ID = (event.queryStringParameters && event.queryStringParameters.ad_account_id) || (JSON.parse(event.body||'{}').ad_account_id) || AD_ACCOUNT_ID;
  const acc = new AdAccount(AD_ACCOUNT_ID);
  const ads = await acc.getAds(['id','name','adset_id'], { effective_status: ['ACTIVE','PAUSED'] });
  const found = ads.find(a => a.name === "CTWA | Ad 1" && a.adset_id === adsetId);
  if (found) return found.id;
  const ad = await acc.createAd({
    name: "CTWA | Ad 1",
    adset_id: adsetId,
    creative: { creative_id: creativeId },
    status: 'PAUSED'
  });
  return ad.id;
}

async function activateAll(campId, adsetId, adIds) {
  await (new Campaign(campId)).update({ status: 'ACTIVE' });
  await (new AdSet(adsetId)).update({ status: 'ACTIVE' });
  for (const aid of adIds) { await (new Ad(aid)).update({ status: 'ACTIVE' }); }
}

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return corsify({ ok: true });
  try {
    requireAuth(event);
    const fbToken = (event.headers && (event.headers['x-fb-token'] || event.headers['X-FB-Token'])) || process.env.FB_ACCESS_TOKEN;
    if (!fbToken) throw new Error("Missing Facebook token (header X-FB-Token or FB_ACCESS_TOKEN).");
    const body = JSON.parse(event.body || "{}");
    const AD_ACCOUNT_ID = (event.queryStringParameters && event.queryStringParameters.ad_account_id) || body.ad_account_id || AD_ACCOUNT_ID;
    const PAGE_ID = (event.queryStringParameters && event.queryStringParameters.page_id) || body.page_id || PAGE_ID;
    const WHATSAPP = (body.whatsapp_number) || WHATSAPP;
    if (!AD_ACCOUNT_ID) throw new Error("Missing ad_account_id (body or env AD_ACCOUNT_ID).");
    if (!PAGE_ID) throw new Error("Missing page_id (body or env PAGE_ID).");
    if (!WHATSAPP) throw new Error("Missing whatsapp_number (body or env WHATSAPP_NUMBER).");
    const accessToken = fbToken;

  if (event.httpMethod === "OPTIONS") return corsify({ ok: true });
  try {
        const accessToken = (event.headers && (event.headers['x-fb-token'] || event.headers['X-FB-Token'])) || process.env.FB_ACCESS_TOKEN;
    FacebookAdsApi.init(accessToken);

    const body = JSON.parse(event.body || "{}");
    const posts = Array.isArray(body.posts) ? body.posts : [];
    let msg_min = parseFloat(body.msg_min || 10);
    let eng_min = parseFloat(body.eng_min || 10);

    // currency offset
    const AD_ACCOUNT_ID = (event.queryStringParameters && event.queryStringParameters.ad_account_id) || (JSON.parse(event.body||'{}').ad_account_id) || AD_ACCOUNT_ID;
    const accInfo = await (new AdAccount(AD_ACCOUNT_ID)).get([ "currency" ]);
    const offset = minorOffsetForCurrency(accInfo.currency || "TND");

    // fix post ids to PAGEID_POSTID
    const fullPosts = posts.map(pid => pid.includes("_") ? pid : `${PAGE_ID}_${pid}`);

    // ENGAGEMENT
    const AD_ACCOUNT_ID = (event.queryStringParameters && event.queryStringParameters.ad_account_id) || (JSON.parse(event.body||'{}').ad_account_id) || AD_ACCOUNT_ID;
    const engCampaign = await ensureCampaign(`${process.env.BRAND || 'Corella Store'} | Engagement`, "ENGAGEMENT", AD_ACCOUNT_ID);
    const engAdSet = await ensureAdSet("TN | 18-45 | FB+IG | Boost", engCampaign, tndToMinor(eng_min, offset), "POST_ENGAGEMENT");
    const engAds = await createEngagementAds(engAdSet, fullPosts);
    await activateAll(engCampaign, engAdSet, engAds);

    // MESSAGES
    const msgCampaign = await ensureCampaign(`${process.env.BRAND || 'Corella Store'} | CTWA | Sales`, "MESSAGES", AD_ACCOUNT_ID);
    const msgAdSet = await ensureAdSet("TN | 18-45 | FB+IG | Messages", msgCampaign, tndToMinor(msg_min, offset), "MESSAGING_CONVERSATIONS");
    const msgCreative = await ensureMsgCreative();
    const msgAd = await ensureMsgAd(msgAdSet, msgCreative);
    await activateAll(msgCampaign, msgAdSet, [msgAd]);

    return corsify({
      ok: true,
      offset,
      engagement: { campaign_id: engCampaign, adset_id: engAdSet, ads: engAds },
      messages:   { campaign_id: msgCampaign, adset_id: msgAdSet, ad_id: msgAd }
    });
  } catch (err) {
    return corsify({ error: err.message || String(err) }, 500);
  }
};

