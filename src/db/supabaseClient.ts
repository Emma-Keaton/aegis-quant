import { createClient } from '@supabase/supabase-js';

// Supabase URL and ANON key should be provided via environment variables.
// In a real deployment these are set in the Render/Supabase dashboard.
const supabaseUrl = process.env.SUPABASE_URL || '';
const supabaseAnonKey = process.env.SUPABASE_ANON_KEY || '';

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('[Supabase] SUPABASE_URL or SUPABASE_ANON_KEY not set – DB operations will fail');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
