import { z } from 'zod';

/**
 * L7: config doc MOT LAN luc khoi dong. Khong co process.env o bat cu dau khac.
 * Thieu bien -> process khong khoi dong duoc (fail fast, khong fail luc 2 gio sang).
 */
export const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),

  OPENAI_API_KEY: z.string().min(1),

  EMBEDDING_PROVIDER: z.string().min(1),
  EMBEDDING_API_KEY: z.string().min(1),
  EMBEDDING_MODEL: z.string().min(1),
  EMBEDDING_DIM: z.coerce.number().int().positive(),
  RERANK_PROVIDER: z.string().min(1),
  RERANK_API_KEY: z.string().min(1),
  RERANK_MODEL: z.string().min(1),
  RERANK_MIN_SCORE: z.coerce.number().min(0).max(1),

  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url(),

  ZALO_BOT_TOKEN: z.string().min(1),
  ZALO_MODE: z.enum(['webhook', 'polling']),
  ZALO_WEBHOOK_SECRET: z.string().min(16),

  META_APP_SECRET: z.string().min(1),
  META_PAGE_TOKEN: z.string().min(1),
  META_VERIFY_TOKEN: z.string().min(1),

  BOT_MENTION_NAME: z.string().min(1),
  GROUP_POLICY: z.enum(['allowlist', 'open', 'disabled']),
  DM_POLICY: z.enum(['pairing', 'allowlist', 'open', 'disabled']),
  RL_USER_PER_MIN: z.coerce.number().int().positive(),
  RL_THREAD_PER_MIN: z.coerce.number().int().positive(),

  // --- Cong cu (giai doan 3) ---
  // De TRONG thi cong cu tuong ung khong duoc khai trong ToolPort.specs(). Cho model
  // thay mot cong cu roi de no goi that bai la cach nhanh nhat de no bia ket qua.
  TAVILY_API_KEY: z.string().default(''),
  SEMANTIC_SCHOLAR_API_KEY: z.string().default(''),

  // Chan cung cua vong ReAct. Thieu cai nao cung thanh vong dot tien khong day.
  REACT_MAX_ITERATIONS: z.coerce.number().int().positive().default(5),
  REACT_MAX_TOOL_CALLS: z.coerce.number().int().positive().default(8),
  REACT_DEADLINE_MS: z.coerce.number().int().positive().default(60_000),

  // --- Giao dien web ---
  WEB_PORT: z.coerce.number().int().positive().default(3000),
  // Chi localhost. Mo ra 0.0.0.0 khi CHUA co auth nghia la ai trong mang cung dot
  // duoc ngan sach cua ban.
  WEB_BIND: z.string().min(1).default('127.0.0.1'),

  // Khong co mac dinh, co chu y. Xem ARCHITECTURE.md section 8.3.
  DAILY_BUDGET_USD: z.coerce.number().positive(),
});

export type Env = z.infer<typeof envSchema>;
