import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createInterface } from 'node:readline/promises';
import { CLI_MAX_MESSAGE_CHARS, normalizeCliInput } from '../adapters/cli/normalize.js';
import { handleMessage } from '../agents/pipeline/handle-message.js';
import type { ChannelPort } from '../agents/ports/channel.port.js';
import { closeDb, query, withTransaction } from '../infra/db.js';
import { logger } from '../infra/logger.js';
import { closeRedis } from '../infra/redis.js';
import { buildContainer } from './container.js';

/**
 * REPL chat + lenh quan tri.
 *
 * CLI la adapter thu ba, khong phai do choi — day la cach duy nhat lam Phase 0 khi
 * chua co token Zalo/Meta.
 *
 * CO Y bo qua hang doi: REPL von tuan tu mot nguoi dung, nen FIFO theo thread da
 * duoc bao dam san. Bat buoc chay them worker chi de go mot cau hoi la lam kho
 * viec phat trien ma khong mua duoc gi.
 */
const MIGRATIONS_DIR = resolve(process.cwd(), 'db/migrations');

async function migrate(): Promise<void> {
  // Bang theo doi phai ton tai TRUOC khi chay 0001 — chinh 0001 cung can duoc ghi
  // lai la da chay. 0005 tao lai bang nay bang CREATE TABLE IF NOT EXISTS.
  await query(`CREATE TABLE IF NOT EXISTS schema_migration (
    filename   TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
  )`);

  const applied = new Set(
    (await query<{ filename: string }>('SELECT filename FROM schema_migration')).map(
      (r) => r.filename,
    ),
  );

  const files = readdirSync(MIGRATIONS_DIR)
    .filter((f) => f.endsWith('.sql'))
    .sort(); // danh so tang dan, chi tien, khong sua file cu

  let ran = 0;
  for (const filename of files) {
    if (applied.has(filename)) continue;

    const sql = readFileSync(resolve(MIGRATIONS_DIR, filename), 'utf8');
    // Mot migration mot transaction: hong giua chung thi khong de lai nua vet.
    await withTransaction(async (client) => {
      await client.query(sql);
      await client.query('INSERT INTO schema_migration (filename) VALUES ($1)', [filename]);
    });
    logger.info({ filename }, 'da chay migration');
    ran += 1;
  }

  logger.info({ ran, total: files.length }, ran === 0 ? 'khong co migration moi' : 'migrate xong');
}

async function chat(): Promise<void> {
  const container = await buildContainer();

  const channel: ChannelPort = {
    maxMessageChars: CLI_MAX_MESSAGE_CHARS,
    async typing() {
      process.stdout.write('...\r');
    },
    async send(_scope, text) {
      process.stdout.write(`\nbot> ${text}\n\n`);
    },
  };

  const rl = createInterface({ input: process.stdin, output: process.stdout });
  console.log('Go cau hoi roi Enter. Ctrl+D hoac Ctrl+C de thoat.\n');

  // rl.question() KHONG resolve khi stdin dong (vd chay bang pipe: echo ... | npm
  // run dev:cli). Khong bat 'close' thi process treo mai ma khong in gi — stdout
  // bi buffer khi la pipe nen nhin nhu chet ngay tu dau.
  let closed = false;
  rl.on('close', () => {
    closed = true;
  });

  while (!closed) {
    let line: string;
    try {
      line = (await rl.question('ban> ')).trim();
    } catch {
      break; // stdin dong giua chung
    }
    if (closed) break;
    if (line === '') continue;

    const msg = normalizeCliInput(line);
    const result = await handleMessage(msg, { ...container, channel });

    if (!result.ok) {
      logger.error({ traceId: msg.traceId, error: result.error }, 'luot chat that bai');
    }
  }

  rl.close();
}

async function main(): Promise<void> {
  const command = process.argv[2] ?? 'chat';

  switch (command) {
    case 'migrate':
      await migrate();
      break;
    case 'chat':
      await chat();
      break;
    default:
      console.error(`Lenh khong biet: ${command}. Co: migrate | chat`);
      process.exitCode = 1;
  }
}

try {
  await main();
} catch (err) {
  logger.error({ err: err instanceof Error ? err.stack : String(err) }, 'cli hong');
  process.exitCode = 1;
} finally {
  // Ca migrate lan chat deu ket thuc duoc, nen luon dong ket noi — con treo mot
  // pool Postgres la process khong bao gio thoat.
  await Promise.allSettled([closeDb(), closeRedis()]);
}
