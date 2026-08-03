import { supabase } from './supabaseClient';

export interface Profile {
  id: string;
  telegram_id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
  language_code?: string;
  wallet_connected: boolean;
  wallet_address?: string;
  wallet_network?: string;
  wallet_public_key?: string;
  risk_level: string;
  max_allocation_pct: number;
  max_concurrent_trades: number;
  trading_mode: 'paper' | 'live';
  bot_enabled: boolean;
  // ... other columns omitted for brevity
}

/** Get a profile by Telegram user ID */
export async function getProfileByTelegramId(telegramId: number): Promise<Profile | null> {
  const { data, error } = await supabase
    .from<Profile>('profiles')
    .select('*')
    .eq('telegram_id', telegramId)
    .single();
  if (error) {
    console.error('[Supabase] getProfileByTelegramId error:', error);
    return null;
  }
  return data ?? null;
}

/** Insert a new profile (used on first start) */
export async function createProfile(data: Partial<Profile> & { telegram_id: number }): Promise<Profile> {
  const { data: row, error } = await supabase.from<Profile>('profiles').insert([data as any]).single();
  if (error) {
    throw new Error('Supabase createProfile error: ' + error.message);
  }
  return row!;
}

/** Update mutable fields of a profile */
export async function updateProfile(telegramId: number, updates: Partial<Profile>): Promise<Profile | null> {
  if (!Object.keys(updates).length) {
    return getProfileByTelegramId(telegramId);
  }
  const { data, error } = await supabase
    .from<Profile>('profiles')
    .update(updates as any)
    .eq('telegram_id', telegramId)
    .single();
  if (error) {
    console.error('[Supabase] updateProfile error:', error);
    return null;
  }
  return data ?? null;
}
