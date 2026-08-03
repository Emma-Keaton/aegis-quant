import { supabase } from './supabaseClient';

export interface RiskSettings {
  profile_id: string;
  stop_loss_pct: number;
  take_profit_pct: number;
  trailing_stop_pct: number;
  max_allocation_pct: number;
  max_concurrent_trades: number;
  max_daily_drawdown_pct: number;
  whitelist_only: boolean;
}

/** Fetch risk settings for a given profile */
export async function getRiskSettings(profileId: string): Promise<RiskSettings | null> {
  const { data, error } = await supabase
    .from<RiskSettings>('risk_settings')
    .select('*')
    .eq('profile_id', profileId)
    .single();
  if (error) {
    console.error('[Supabase] getRiskSettings error:', error);
    return null;
  }
  return data ?? null;
}

/** Upsert risk settings (used by the front‑end when updating) */
export async function upsertRiskSettings(profileId: string, settings: Partial<RiskSettings>): Promise<RiskSettings> {
  if (!Object.keys(settings).length) {
    const existing = await getRiskSettings(profileId);
    if (!existing) throw new Error('RiskSettings not found for profile');
    return existing;
  }
  const upsertData = { profile_id: profileId, ...settings } as any;
  const { data, error } = await supabase.from<RiskSettings>('risk_settings').upsert(upsertData, { onConflict: 'profile_id' }).single();
  if (error) {
    throw new Error('Supabase upsertRiskSettings error: ' + error.message);
  }
  return data!;
}
