const supabase = require('../config/database');

const CACHE_TABLE = 'api_cache';
const DEFAULT_TTL = parseInt(process.env.CACHE_TTL_MINUTES) || 30;

class CacheService {
  async get(key) {
    try {
      const { data, error } = await supabase
        .from(CACHE_TABLE)
        .select('*')
        .eq('cache_key', key)
        .single();

      if (error || !data) return null;

      const now = new Date();
      const expiresAt = new Date(data.expires_at);
      
      if (now > expiresAt) {
        await supabase.from(CACHE_TABLE).delete().eq('cache_key', key);
        return null;
      }

      return JSON.parse(data.data);
    } catch (err) {
      console.error('Cache get error:', err.message);
      return null;
    }
  }

  async set(key, data, ttlMinutes = DEFAULT_TTL) {
    try {
      const expiresAt = new Date(Date.now() + ttlMinutes * 60 * 1000);
      
      const { error } = await supabase
        .from(CACHE_TABLE)
        .upsert({
          cache_key: key,
          data: JSON.stringify(data),
          expires_at: expiresAt.toISOString(),
          created_at: new Date().toISOString()
        }, { onConflict: 'cache_key' });

      if (error) throw error;
      return true;
    } catch (err) {
      console.error('Cache set error:', err.message);
      return false;
    }
  }

  async clear(key) {
    try {
      if (key) {
        await supabase.from(CACHE_TABLE).delete().eq('cache_key', key);
      } else {
        await supabase.from(CACHE_TABLE).delete().neq('cache_key', '');
      }
      return true;
    } catch (err) {
      console.error('Cache clear error:', err.message);
      return false;
    }
  }
}

module.exports = new CacheService();
