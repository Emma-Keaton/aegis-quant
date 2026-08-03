import { Bot, Context } from 'grammy';
import fetch from 'node-fetch';
import { notifyTradeExecution } from './telegramBot';

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
if (!BOT_TOKEN) {
  console.error('[Bot] TELEGRAM_BOT_TOKEN is not set – bot will not start');
  process.exit(1);
}

const bot = new Bot(BOT_TOKEN);

// Simple /start command
bot.command('start', async (ctx) => {
  await ctx.reply('🤖 Aegis Quant bot ready. Use /help for commands.');
});

// /help command – list available actions
bot.command('help', async (ctx) => {
  const helpText = `Available commands:
/start – welcome
/profile – view your profile
/mode – toggle paper/live mode
/toggle_bot – enable/disable the trading agent
`; 
  await ctx.reply(helpText);
});

// Helper to extract telegram user ID from Gram­my context
function getTelegramUserId(ctx: Context): number | null {
  return ctx.from?.id ?? null;
}

// /profile – fetch profile from backend
bot.command('profile', async (ctx) => {
  const userId = getTelegramUserId(ctx);
  if (!userId) return ctx.reply('Could not identify you');
  const url = `${process.env.APP_URL}/api/state`;
  const res = await fetch(url, {
    headers: { 'x-telegram-init-data': `user=${JSON.stringify({ id: userId })}` },
  });
  const json = await res.json();
  if (json.error) return ctx.reply('Profile not found');
  const profile = json.data;
  await ctx.reply(`📊 Profile\nTrading mode: ${profile.tradeMode}\nAgent active: ${profile.agentActive}`);
});

// /mode – toggle paper/live mode (expects 'paper' or 'live' as argument)
bot.command('mode', async (ctx) => {
  const args = ctx.message.text.split(' ').slice(1);
  const mode = args[0]?.toUpperCase();
  if (!['PAPER', 'LIVE'].includes(mode)) {
    return ctx.reply('Usage: /mode paper|live');
  }
  const userId = getTelegramUserId(ctx);
  if (!userId) return ctx.reply('User unknown');
  const url = `${process.env.APP_URL}/api/toggle-mode`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': `user=${JSON.stringify({ id: userId })}` },
    body: JSON.stringify({ mode: mode }),
  });
  const json = await res.json();
  await ctx.reply(json.status === 'success' ? `Mode switched to ${mode}` : 'Failed to switch mode');
});

// /toggle_bot – enable or disable the AI trading agent (expects 'on' or 'off')
bot.command('toggle_bot', async (ctx) => {
  const args = ctx.message.text.split(' ').slice(1);
  const on = args[0] === 'on';
  const userId = getTelegramUserId(ctx);
  if (!userId) return ctx.reply('User unknown');
  const url = `${process.env.APP_URL}/api/toggle-agent`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-telegram-init-data': `user=${JSON.stringify({ id: userId })}` },
    body: JSON.stringify({ active: on }),
  });
  const json = await res.json();
  await ctx.reply(json.status === 'success' ? `Agent ${on ? 'enabled' : 'disabled'}` : 'Failed');
});

// Example: receive a custom webhook from backend to forward a trade notification
// (Backend can POST to /api/bot/notify with JSON {chatId, trade})
bot.on('message:unknown', async (ctx) => {
  // placeholder – real notifications are sent via notifyTradeExecution directly.
});

// Start polling (or webhook if you configure it elsewhere)
bot.start();

export default bot;
