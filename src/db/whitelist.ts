import { supabase } from './supabaseClient';

export interface WhitelistEntry {
  profile_id: string;
  symbol: string;
  exchange: string;
  timeframe: string;
  active: boolean;
  added_at: string;
}

/** Get all active whitelist entries for a profile */
export async function getActiveWhitelist(profileId: string): Promise<WhitelistEntry[]> {
  const { data, error } = await supabase
    .from<WhitelistEntry>('user_whitelist')
    .select('*')
    .eq('profile_id', profileId)
    .eq('active', true);
  if (error) {
    console.error('[Supabase] getActiveWhitelist error:', error);
    return [];
  }
  return data ?? [];
}

/** Add or upsert a whitelist entry (used by the UI) */
export async function upsertWhitelist(entry: {
  profile_id: string;
  symbol: string;
  exchange?: string;
  timeframe?: string;
  active?: boolean;
  target_price?: number;
  direction?: 'above' | 'below';
}): Promise<WhitelistEntry> {
  const {
    profile_id,
    symbol,
    exchange = 'bybit',
    timeframe = '1m',
    active = true,
    target_price,
    direction,
  } = entry;

  const upsertData: any = {
    profile_id,
    symbol,
    exchange,
    timeframe,
    active,
    target_price,
    direction,
  };

  const { data, error } = await supabase
    .from<WhitelistEntry>('user_whitelist')
    .upsert(upsertData, { onConflict: 'profile_id,symbol,exchange' })
    .single();
  if (error) {
    throw new Error('Supabase upsertWhitelist error: ' + error.message);
  }
  return data!;
}

/** Remove (deactivate) a whitelist entry */
export async function deactivateWhitelist(profileId: string, symbol: string, exchange: string): Promise<void> {
  const { error } = await supabase
    .from('user_whitelist')
    .update({ active: false })
    .eq('profile_id', profileId)
    .eq('symbol', symbol)
    .eq('exchange', exchange);
  if (error) {
    console.error('[Supabase] deactivateWhitelist error:', error);
  }
}
