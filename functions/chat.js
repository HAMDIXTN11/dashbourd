
const fetch = global.fetch || ((...args) => import('node-fetch').then(({default: f}) => f(...args)));

// Proxy Chat with OpenAI (GPT-5) + function-calling to our existing Netlify functions.
// Requires env: OPENAI_API_KEY
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

function requireAuth(event) {
  const token = process.env.ADMIN_TOKEN;
  if (!token) return; // disabled
  const hdr = (event.headers && (event.headers.authorization || event.headers.Authorization)) || "";
  const ok = hdr.startsWith("Bearer ") && hdr.slice(7) === token;
  if (!ok) { const e = new Error("Unauthorized"); e.statusCode = 401; throw e; }
}

async function callOpenAI(payload) {
  if (!process.env.OPENAI_API_KEY) throw new Error("Missing OPENAI_API_KEY");
  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${process.env.OPENAI_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`OpenAI error ${res.status}: ${t}`);
  }
  return await res.json();
}

async function handleToolCall(toolCall, ctx) {
  const name = toolCall.function.name;
  let args = {};
  try { args = JSON.parse(toolCall.function.arguments || "{}"); } catch (e) {}
  const headers = Object.assign(
    { "Content-Type": "application/json" },
    ctx.fbToken ? { "X-FB-Token": ctx.fbToken } : {},
    ctx.adminHeader ? { "Authorization": ctx.adminHeader } : {}
  );

  if (name === "list_posts") {
    const url = `/.netlify/functions/list_posts?page_id=${encodeURIComponent(args.page_id || ctx.page_id)}`;
    const r = await fetch(url, { headers });
    return await r.json();
  }
  if (name === "run_setup") {
    const payload = {
      posts: args.posts || ctx.posts || [],
      msg_min: args.msg_min ?? 10,
      eng_min: args.eng_min ?? 10,
      ad_account_id: args.ad_account_id || ctx.ad_account_id,
      page_id: args.page_id || ctx.page_id,
      brand: args.brand || ctx.brand || "Corella Store",
      whatsapp_number: args.whatsapp_number || ctx.whatsapp_number
    };
    const r = await fetch("/.netlify/functions/setup", { method: "POST", headers, body: JSON.stringify(payload) });
    return await r.json();
  }
  if (name === "run_optimize") {
    const payload = {
      msg_min: args.msg_min ?? 10, msg_max: args.msg_max ?? 200, msg_target_cpa: args.msg_target_cpa ?? 2.5,
      eng_min: args.eng_min ?? 10, eng_max: args.eng_max ?? 150, eng_target_cpe: args.eng_target_cpe ?? 0.2,
      ad_account_id: args.ad_account_id || ctx.ad_account_id, brand: args.brand || ctx.brand || "Corella Store"
    };
    const r = await fetch("/.netlify/functions/optimize", { method: "POST", headers, body: JSON.stringify(payload) });
    return await r.json();
  }
  return { error: `Unknown tool: ${name}` };
}

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return corsify({ ok: true });
  try {
    requireAuth(event);
    const body = JSON.parse(event.body || "{}");
    const messages = Array.isArray(body.messages) ? body.messages : [];
    const fbToken = (event.headers && (event.headers['x-fb-token'] || event.headers['X-FB-Token'])) || null;
    const adminHeader = (event.headers && (event.headers.authorization || event.headers.Authorization)) || null;

    const ctx = {
      fbToken,
      adminHeader,
      ad_account_id: body.ad_account_id,
      page_id: body.page_id,
      whatsapp_number: body.whatsapp_number,
      brand: body.brand || "Corella Store",
      posts: body.posts || []
    };

    // System prompt specialized for Hamdi's use case
    const system = {
      role: "system",
      content: [
        "You are 'Corella Copilot', a Tunisian-market ads assistant.",
        "Goals: Increase WhatsApp conversations (CTWA) and Boost Post engagement for Corella Store.",
        "Be concise, bilingual when helpful (Tunisian Arabic + French), and return clear steps.",
        "If a user asks to execute an action, prefer calling a tool (run_setup, run_optimize, list_posts).",
        "Targets: default CPA=2.5 DT for messages, CPE=0.2 DT for engagement, age 18–45, country TN.",
        "When recommending budgets, use daily DT ranges and explain in one line.",
        "Never expose secrets. If missing IDs or token, politely ask for login/selection."
      ].join(" ")
    };

    const tools = [
      {
        type: "function",
        function: {
          name: "list_posts",
          description: "List last 25 posts for a given Page",
          parameters: { type: "object", properties: { page_id: { type: "string" } }, required: [] }
        }
      },
      {
        type: "function",
        function: {
          name: "run_setup",
          description: "Create/activate Messages (CTWA) and Engagement campaigns for selected posts",
          parameters: {
            type: "object",
            properties: {
              posts: { type: "array", items: { type: "string" } },
              msg_min: { type: "number" },
              eng_min: { type: "number" },
              ad_account_id: { type: "string" },
              page_id: { type: "string" },
              brand: { type: "string" },
              whatsapp_number: { type: "string" }
            },
            required: ["ad_account_id", "page_id"]
          }
        }
      },
      {
        type: "function",
        function: {
          name: "run_optimize",
          description: "Optimize budgets for Messages/Engagement ad sets based on yesterday performance",
          parameters: {
            type: "object",
            properties: {
              msg_min: { type: "number" }, msg_max: { type: "number" }, msg_target_cpa: { type: "number" },
              eng_min: { type: "number" }, eng_max: { type: "number" }, eng_target_cpe: { type: "number" },
              ad_account_id: { type: "string" }, brand: { type: "string" }
            },
            required: ["ad_account_id"]
          }
        }
      }
    ];

    // First turn
    let payload = {
      model: "gpt-5", // you can switch to gpt-5-mini to save cost
      temperature: 0.2,
      tools,
      messages: [system, ...messages]
    };

    let resp = await callOpenAI(payload);
    let outMessages = [];
    let finalText = "";
    let toolRuns = [];

    const choice = resp.choices && resp.choices[0];
    if (choice && choice.message) {
      // Handle tool calls if any
      const m = choice.message;
      if (m.tool_calls && m.tool_calls.length) {
        for (const tc of m.tool_calls) {
          const result = await handleToolCall(tc, ctx);
          toolRuns.push({ name: tc.function.name, result });
          // feed tool result back
          payload.messages.push({ role: "assistant", tool_calls: [tc] });
          payload.messages.push({ role: "tool", tool_call_id: tc.id, content: JSON.stringify(result) });
        }
        // Ask model to summarize outcomes for user
        payload.messages.push({ role: "user", content: "خلاصة عمّا صار + next steps مختصرة." });
        resp = await callOpenAI(payload);
        finalText = resp.choices?.[0]?.message?.content || "OK";
      } else {
        finalText = m.content || "OK";
      }
    }

    return corsify({ ok: true, message: finalText, tools: toolRuns });
  } catch (err) {
    const code = err.statusCode || 500;
    return corsify({ error: err.message || String(err) }, code);
  }
};
