# Optional result reports

**English** · the user-facing text of the dialogs is bilingual (es/en).

`tvlite` can send the maintainer an **anonymous report of how it went**, so the README and the device lists can be improved with real results (what worked, and on failure the TV model, Android, SoC, RAM and the error).

## It is opt-in. Nothing is ever sent automatically

- When a run finishes, `tvlite` shows **the exact content** it would send and asks. Only if the user presses **Send** (GUI) or answers `s`/`y` (CLI) is anything sent. **No** is the default, and `--yes` on its own never sends.
- `tvlite apply ... --send-report` is an explicit consent for scripted use; it still prints the content first.
- If no relay is configured (the default in this repository) the feature is **inactive and never offered**.
- `tvlite report <ip>` (the manual report for GitHub issues) is separate and **sends nothing**.

## What is included

```jsonc
{
  "schema": 1, "tvlite": "0.1.0", "kind": "success | partial | failure",
  "pc": { "os": "Windows", "release": "11", "arch": "AMD64", "frozen": true },
  "tv": { "manufacturer": "TCL", "model": "Smart TV", "android": "11", "sdk": 30, "soc": "mt5867",
          "abis": ["armeabi-v7a"], "ram_mb": 917, "profile": "ultra_low", "play_store": true,
          "storage_free_mb": 1451, "resolution": "1280x720", "density": 213, "simulated": false },
  "result": { "removed": ["com.tcl.esticker", "..."], "removed_count": 12, "failed": [], "rolled_back": 0,
              "aborted": false, "apps": { "stremio": "ok" }, "launcher": "ok", "dry_run": false },
  "metrics": { "before": { "ram_available_mb": 292, "packages": 14 }, "after": { "ram_available_mb": 341, "packages": 9 } },
  "error": ""            // on failure: the error and traceback, with personal data removed
}
```

## What is never included

User-installed apps, accounts, the name of your Wi-Fi network, the TV's serial number, any persistent identifier. Before an error text is shown or sent, these are replaced: **IP addresses, MAC addresses, Windows/macOS/Linux user names and home paths, and long hexadecimal identifiers** (`<ip>`, `<mac>`, `~`, `<user>`, `<id>`). The dialog shows the text **after** this cleanup, so what you read is what is sent. (The relay still sees the sender's IP at the network level, as any web server does; it hashes it only to rate-limit and does not store it in clear.)

## Architecture and why a relay

```
tvlite (user's PC)  --HTTPS POST, JSON-->  relay (Cloudflare Worker)  --Telegram Bot API-->  maintainer's chat
```

The Telegram **bot token must not be inside the program**: this project is open source, so anyone could extract it and control the bot. Only the relay holds it (as a Worker secret). The relay also:

- accepts only `POST` with a `tvlite/*` user agent, JSON ≤ 12 KB with the exact schema above;
- **builds the Telegram message itself** from validated fields (the client cannot send free text to the bot) and sends it as plain text, so nothing received is interpreted as formatting;
- rate-limits per IP (hashed) when a KV namespace is bound.

## Setting it up (maintainer)

1. **Bot**: create it with [@BotFather](https://t.me/BotFather) (done: `@tv_android_cleaner_bot`). Send `/start` to your bot from your own account.
2. **Chat id**: after `/start`, open `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id` (or ask the person who runs the setup to do it for you).
3. **Relay on Cloudflare Workers** (a free Cloudflare account is enough; nothing to maintain). Needs Node.js:
   ```bash
   cd tools/telemetry-relay
   npx wrangler login                           # opens the browser: sign in to Cloudflare
   npx wrangler kv namespace create RATE        # paste the id into wrangler.toml (recommended: rate limit)
   npx wrangler deploy                          # prints https://tvlite-relay.<you>.workers.dev
   npx wrangler secret put TELEGRAM_BOT_TOKEN   # it asks for the value: paste the token there, never in a file or chat
   npx wrangler secret put TELEGRAM_CHAT_ID
   ```
   *Alternative without Cloudflare:* run `tools/telemetry-relay/server.py` on a server you own, with the token in a `.env` that only exists there (`.env.example`; `.env` is git-ignored). It gives the same messages (a test checks the parity).
4. **Point tvlite to it**: set `DEFAULT_REPORT_URL` in `installer/tvlite/telemetry.py` to that URL (it is public by design; it contains no secret) and release. For tests, `TVLITE_REPORT_URL` overrides it.
5. **Test the relay** without tvlite:
   ```bash
   curl -X POST "$RELAY_URL" -H "User-Agent: tvlite/0.1.0" -H "Content-Type: application/json" \
     -d '{"schema":1,"tvlite":"0.1.0","kind":"success","pc":{"os":"test"},"tv":{"model":"relay test"}}'
   ```
   You should receive a message in Telegram and an empty `204` response.
6. **Rotate the token if it was ever pasted anywhere** (chat, issue, log): `/revoke` in @BotFather, then `wrangler secret put TELEGRAM_BOT_TOKEN` with the new one.

## Privacy notes for the maintainer

- Reports contain device and error data only, but you are still processing data that users chose to send you: say so in the dialog (it does) and in the README, keep messages only as long as needed and delete them when no longer useful (delete the chat history in Telegram).
- Do not add persistent install ids, IP logging or anything that would make a report identify a person. Any new field must be added to the schema in `telemetry.py`, to this document **and** to `worker.js`.
