// Relé de informes de tvlite -> Telegram (Cloudflare Worker).
//
// Por que existe: el token de un bot de Telegram NO puede ir dentro de un programa de codigo abierto (cualquiera lo
// extraeria y controlaria el bot). El programa envia el informe anonimo A ESTE RELÉ y solo el relé conoce el token.
//
// Secretos (wrangler secret put ...): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
// Opcional (limite de envios por IP): un KV con binding RATE.
//
// El relé construye el mensaje él mismo a partir de campos validados (el cliente no puede mandar texto libre
// al bot) y lo envia como texto plano (sin parse_mode), asi que nada de lo recibido se interpreta como formato.

const MAX_BYTES = 12000;
const MAX_TEXT = 3900; // Telegram admite 4096
const RATE_LIMIT_PER_HOUR = 30;
const KINDS = new Set(["success", "partial", "failure"]);

const str = (v, max = 120) => (typeof v === "string" ? v.slice(0, max) : "");
const num = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

function valid(ev) {
  return (
    ev && typeof ev === "object" && ev.schema === 1 && KINDS.has(ev.kind) &&
    typeof ev.tvlite === "string" && ev.tv && typeof ev.tv === "object" && ev.pc && typeof ev.pc === "object"
  );
}

export function format(ev) {
  const icon = { success: "✅", partial: "⚠️", failure: "❌" }[ev.kind];
  const label = { success: "OK", partial: "PARCIAL", failure: "FALLO" }[ev.kind];
  const tv = ev.tv || {};
  const pc = ev.pc || {};
  const name = [str(tv.manufacturer || tv.brand), str(tv.model)].filter(Boolean).join(" ") || "tele desconocida";
  const lines = [
    `${icon} tvlite ${label} - ${name}${tv.simulated ? " (SIMULADA)" : ""}`,
    `Android ${str(tv.android, 20)} (API ${num(tv.sdk) ?? "?"}) | SoC ${str(tv.soc, 40) || "?"} | ` +
      `ABI ${(Array.isArray(tv.abis) ? tv.abis.map((a) => str(a, 20)).join(",") : "") || "?"}`,
    `RAM ${num(tv.ram_mb) ?? "?"} MB (${str(tv.profile, 20)}) | libre ${num(tv.storage_free_mb) ?? "?"} MB | ` +
      `${str(tv.resolution, 20)} | Play Store: ${tv.play_store === false ? "NO" : "si"}`,
    `PC: ${str(pc.os, 20)} ${str(pc.release, 20)} ${str(pc.arch, 20)}${pc.frozen ? " (ejecutable)" : ""} | tvlite ${str(ev.tvlite, 20)}`,
  ];
  const r = ev.result;
  if (r && typeof r === "object") {
    const apps = r.apps && typeof r.apps === "object"
      ? Object.entries(r.apps).slice(0, 30).map(([k, v]) => `${str(k, 30)}:${v === "ok" ? "ok" : "FALLO"}`).join(" ")
      : "";
    lines.push(
      `Quitados ${num(r.removed_count) ?? 0}${r.dry_run ? " (simulacion)" : ""} | fallos ${Array.isArray(r.failed) ? r.failed.length : 0}` +
        ` | revertidos ${num(r.rolled_back) ?? 0}${r.aborted ? " | ABORTADO" : ""}`,
      `Launcher: ${str(r.launcher, 160)}${apps ? ` | Apps: ${apps}` : ""}`,
    );
    if (Array.isArray(r.failed) && r.failed.length) {
      lines.push("No se pudo quitar: " + r.failed.slice(0, 8).map((f) => `${str(f && f.pkg, 80)} (${str(f && f.why, 60)})`).join("; "));
    }
  }
  const m = ev.metrics;
  if (m && m.before && m.after) {
    lines.push(`RAM disponible ${num(m.before.ram_available_mb)} -> ${num(m.after.ram_available_mb)} MB | paquetes ${num(m.before.packages)} -> ${num(m.after.packages)}`);
  }
  const error = str(ev.error, 1600);
  if (error) lines.push("", "Error:", error);
  return lines.join("\n").slice(0, MAX_TEXT);
}

async function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function rateLimited(env, request) {
  if (!env.RATE) return false; // sin KV no se limita (configurarlo es recomendable)
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const key = `ip:${(await sha256Hex(ip)).slice(0, 24)}:${new Date().toISOString().slice(0, 13)}`; // por hora; la IP no se guarda en claro
  const count = parseInt((await env.RATE.get(key)) || "0", 10);
  if (count >= RATE_LIMIT_PER_HOUR) return true;
  await env.RATE.put(key, String(count + 1), { expirationTtl: 7200 });
  return false;
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return new Response("method not allowed", { status: 405 });
    if (!(request.headers.get("User-Agent") || "").startsWith("tvlite/")) return new Response("forbidden", { status: 403 });
    const body = await request.text();
    if (body.length > MAX_BYTES) return new Response("payload too large", { status: 413 });
    let ev;
    try { ev = JSON.parse(body); } catch { return new Response("bad json", { status: 400 }); }
    if (!valid(ev)) return new Response("invalid event", { status: 400 });
    if (await rateLimited(env, request)) return new Response("too many requests", { status: 429 });

    const reply = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text: format(ev), disable_web_page_preview: true }),
    });
    if (reply.ok) return new Response(null, { status: 204 });
    // Diagnostico para el mantenedor: estado y descripcion que da Telegram (p. ej. "401 Unauthorized" = token
    // incorrecto, "400 chat not found" = id de chat incorrecto). No contiene secretos.
    let why = "";
    try { why = String((await reply.json()).description || "").slice(0, 120); } catch { /* sin cuerpo */ }
    return new Response(`telegram ${reply.status} ${why}`, { status: 502 });
  },
};
