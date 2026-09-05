import type { Deps } from '../agents/pipeline/handle-message.js';
import type { KnowledgePort } from '../agents/ports/knowledge.port.js';
import type { MemoryPort } from '../agents/ports/memory.port.js';
import { accessRules } from '../config/policy.js';
import { config } from '../config/index.js';
import { query } from '../infra/db.js';
import { logger } from '../infra/logger.js';
import { rateLimit } from '../infra/ratelimit.js';
import { llm } from '../llm/openai.client.js';
import { MODELS } from '../llm/models.js';
import { messageRepo } from '../memory/repository/message.repo.js';
import { toolPort } from '../tools/index.js';

/**
 * Dependency injection thu cong. Mot ham tra ve object — nhin la biet cai gi noi
 * vao cai gi. Khong dung framework DI.
 *
 * `channel` KHONG nam o day: moi entrypoint tu cam kenh cua minh vao (CLI in ra
 * terminal, worker gui qua adapter cua tung nen tang).
 */
export type Container = Omit<Deps, 'channel'>;

/** Section 6.1 chot 15 tin gan nhat cho L1. */
const RECENT_LIMIT = 15;

export async function buildContainer(): Promise<Container> {
  await assertEmbeddingDim();

  const memory: MemoryPort = {
    append: messageRepo.append,
    recent: messageRepo.recent,
    // TODO(tuan-5): L2 va L3. Tra ve rong chu KHONG nem loi — duong ong tuan 1
    // phai chay duoc ma khong co memory ngu nghia.
    summary: async () => null,
    facts: async () => [],
    remember: async () => undefined,
    forget: async () => [],
    list: async () => [],
  };

  // TODO(tuan-4): knowledge/retrieve. Rong = "khong tim thay trong tai lieu",
  // dung nghia hop dong cua port, nen tuan 1 khong can nhanh dac biet nao.
  const knowledge: KnowledgePort = { search: async () => [] };

  const specs = toolPort.specs();
  logger.info(
    { tools: specs.map((s) => s.name) },
    specs.length === 0 ? 'khong co cong cu nao duoc bat' : 'cong cu da san sang',
  );

  return {
    llm,
    memory,
    knowledge,
    tools: toolPort,
    rateLimit,
    clock: { now: () => new Date() },
    logger,
    accessRules,
    botName: config.BOT_MENTION_NAME,
    reply: { maxTokens: MODELS.reply.maxTokens, effort: MODELS.reply.effort },
    react: {
      maxIterations: config.REACT_MAX_ITERATIONS,
      maxToolCalls: config.REACT_MAX_TOOL_CALLS,
      deadlineMs: config.REACT_DEADLINE_MS,
    },
    recentLimit: RECENT_LIMIT,
  };
}

/**
 * Chan cung: so chieu model embedding phai khop cot VECTOR(n) trong DB.
 *
 * Khong co buoc nay, loi se hien ra duoi dang "ket qua tim kiem kem" — ba tuan sau.
 */
async function assertEmbeddingDim(): Promise<void> {
  if (config.EMBEDDING_PROVIDER === 'fake') {
    logger.warn('EMBEDDING_PROVIDER=fake — bo qua kiem tra so chieu, RAG chua bat');
    return;
  }

  // atttypmod cua cot vector = so chieu + 4 (header cua kieu).
  const rows = await query<{ dim: number }>(
    `SELECT atttypmod - 4 AS dim
       FROM pg_attribute
      WHERE attrelid = 'kb_chunk'::regclass AND attname = 'embedding'`,
  );

  const dim = rows[0]?.dim;
  if (dim !== config.EMBEDDING_DIM) {
    throw new Error(
      `So chieu embedding lech: config.EMBEDDING_DIM=${config.EMBEDDING_DIM} ` +
        `nhung cot kb_chunk.embedding la VECTOR(${dim}). ` +
        'Doi so chieu la mot migration moi, khong phai doi bien moi truong.',
    );
  }
}
