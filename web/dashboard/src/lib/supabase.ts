import { createClient } from '@supabase/supabase-js'

// These are safe to expose — the anon key is meant for client-side use.
// The JWT secret (used for server-side validation) is NEVER exposed here.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
