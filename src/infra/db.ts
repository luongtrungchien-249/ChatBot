import pg from 'pg';
import { config } from '../config/index.js';
import { logger } from './logger.js';

/**
 * Mot noi duy nhat mo ket noi Postgres. Postgres la NGUON THAT cho L1/L2/L3/L4;
 * Redis chi la cache doc (xem ARCHITECTURE.md section 6.1).
 */
export const pool = new pg.Pool({
  connectionString: config.DATABASE_URL,
  max: 10,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
  // Chan cau truy van chay mai. Vector search hong van phai tra loi trong ngan sach latency.
  statement_timeout: 10_000,
});

pool.on('error', (err: Error) => logger.error({ err: err.message }, 'postgres pool loi'));

/**
 * L6: moi loi goi ra ngoai co log va do thoi gian. Khong biet cai gi cham
 * thi khong toi uu duoc cai gi.
 */
export async function query<T extends pg.QueryResultRow>(
  text: string,
  params: readonly unknown[] = [],
): Promise<T[]> {
  const started = Date.now();
  try {
    const res = await pool.query<T>(text, params as unknown[]);
    logger.debug({ ms: Date.now() - started, rows: res.rowCount }, 'sql');
    return res.rows;
  } catch (err) {
    logger.error(
      { ms: Date.now() - started, sql: text, err: err instanceof Error ? err.message : String(err) },
      'sql loi',
    );
    throw err;
  }
}

/** Chay nhieu cau trong mot transaction. Dung cho migrate va cac ghi nhieu bang. */
export async function withTransaction<T>(fn: (c: pg.PoolClient) => Promise<T>): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const out = await fn(client);
    await client.query('COMMIT');
    return out;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

export async function closeDb(): Promise<void> {
  await pool.end();
}
