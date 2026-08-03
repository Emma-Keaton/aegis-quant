import { Pool } from 'pg';

// Create a singleton PG pool using the DATABASE_URL environment variable.
// Render (and local dev) provide the URL in the standard format.
// Fallback: if DATABASE_URL is missing, gracefully degrade to allow dev-only mode
// (all state will be in-memory via server.ts dbState)
const connectionString = process.env.DATABASE_URL;
if (!connectionString) {
  console.warn('[DB] DATABASE_URL not set — database operations will fail. Ensure .env is configured.');
}

const pool = new Pool({
  connectionString,
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

export default pool;
