// Using global fetch (available in Node 18+); no external dependency

/**
 * Simple Telegram notification helper for the Aegis Quant mini‑app.
 * Uses the `grammy` bot token stored in the environment variable `TELEGRAM_BOT_TOKEN`.
 * The helper posts messages via the Telegram Bot HTTP API – no long‑running bot
 * process is needed because the backend already receives webhook events.
 */

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
if (!BOT_TOKEN) {
  console.warn('[TelegramBot] TELegram bot token not configured – notifications disabled');
}

/**
 * Send a plain text message to a specific chat.
 * @param chatId Telegram chat identifier (numeric string or number).
 * @param text   Message text (markdown supported).
 */
export async function sendTelegramMessage(chatId: string | number, text: string): Promise<void> {
  if (!BOT_TOKEN) return; // silent no‑op when token missing (useful for local dev).
  const url = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text, parse_mode: 'Markdown' }),
    });
    if (!res.ok) {
      console.error('[TelegramBot] sendMessage failed', res.status, await res.text());
    }
  } catch (err) {
    console.error('[TelegramBot] sendMessage exception', err);
  }
}

/**
 * Convenience wrapper to notify the user about a trade execution.
 * Expects the `trade` object produced by the Gemini execution schema.
 */
export async function notifyTradeExecution(
  trade: { pair: string; size: number; price: number; action: string },
  chatId: string | number
): Promise<void> {
  // Chat ID must be provided explicitly per user.
  const msg = `*Trade executed*\nPair: ${trade.pair}\nAction: ${trade.action}\nSize: ${trade.size}\nPrice: ${trade.price}`;
  await sendTelegramMessage(chatId, msg);
}

export default { sendTelegramMessage, notifyTradeExecution };
