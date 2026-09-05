import type { CallContext, ToolCall } from '../agents/ports/llm.port.js';
import type { ToolDefinition, ToolPort, ToolResult } from '../agents/ports/tool.port.js';
import { logger } from '../infra/logger.js';
import { wrapObservation } from './guard.js';
import { PAPER_SEARCH_DEFINITION, runPaperSearch } from './paper-search.js';
import { isWebSearchAvailable, runWebSearch, WEB_SEARCH_DEFINITION } from './web-search.js';

/**
 * Implement ToolPort. Day la NOI DUY NHAT biet ten cac nha cung cap cong cu —
 * agents/ chi thay ToolPort.
 */
type Runner = (input: Record<string, unknown>, traceId: string) => Promise<string>;

type Registration = Readonly<{
  definition: ToolDefinition;
  run: Runner;
  /** Nguon ghi vao the <ket_qua_cong_cu nguon="..."> */
  source: string;
  /** Thieu khoa thi khong khai trong specs(). */
  available: () => boolean;
}>;

const REGISTRY: readonly Registration[] = [
  {
    definition: WEB_SEARCH_DEFINITION,
    run: async (input) => runWebSearch(input),
    source: 'Tavily',
    available: isWebSearchAvailable,
  },
  {
    definition: PAPER_SEARCH_DEFINITION,
    run: runPaperSearch,
    source: 'OpenAlex + arXiv + Semantic Scholar + Crossref',
    // Ba trong bon nguon khong can khoa nao ca.
    available: () => true,
  },
  // TODO(giai-doan-6): search_knowledge_base — chi khai khi RAG da chay.
];

export const toolPort: ToolPort = {
  specs(): readonly ToolDefinition[] {
    return REGISTRY.filter((r) => r.available()).map((r) => r.definition);
  },

  /**
   * Chay TAT CA loi goi dong thoi va tra ve DU so ket qua.
   *
   * Hai luat de sai:
   *   - Thieu mot toolCallId la ca request tiep theo 400. Cong cu hong van phai co
   *     mot ket qua, danh dau la loi.
   *   - Tra ket qua trong MOT luot. Tach ra nhieu message se am tham day model thoi
   *     goi song song.
   */
  async callMany(calls: readonly ToolCall[], ctx: CallContext): Promise<readonly ToolResult[]> {
    return Promise.all(calls.map((call) => runOne(call, ctx)));
  },
};

async function runOne(call: ToolCall, ctx: CallContext): Promise<ToolResult> {
  const started = Date.now();
  const registration = REGISTRY.find((r) => r.definition.name === call.name);

  if (registration === undefined || !registration.available()) {
    logger.warn({ traceId: ctx.traceId, tool: call.name }, 'model goi cong cu khong ton tai');
    return {
      toolCallId: call.id,
      name: call.name,
      content: `Công cụ "${call.name}" không tồn tại hoặc chưa được bật. Hãy trả lời bằng kiến thức sẵn có và nói rõ là không tra cứu được.`,
      ok: false,
      latencyMs: Date.now() - started,
    };
  }

  try {
    logger.info({ traceId: ctx.traceId, tool: call.name, input: call.input }, 'goi cong cu');
    const raw = await registration.run(call.input, ctx.traceId);
    const latencyMs = Date.now() - started;

    logger.info({ traceId: ctx.traceId, tool: call.name, latencyMs }, 'cong cu tra ve');

    return {
      toolCallId: call.id,
      name: call.name,
      // Boc + sanitize + cat tran. Ket qua cong cu la van ban do NGUOI LA soan.
      content: wrapObservation({
        toolName: call.name,
        source: registration.source,
        content: raw,
        traceId: ctx.traceId,
      }),
      ok: true,
      latencyMs,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const latencyMs = Date.now() - started;
    logger.error({ traceId: ctx.traceId, tool: call.name, latencyMs, err: message }, 'cong cu loi');

    return {
      toolCallId: call.id,
      name: call.name,
      content: `Công cụ "${call.name}" gặp lỗi: ${message}. Hãy nói thẳng với người dùng là chưa tra cứu được, đừng bịa kết quả.`,
      ok: false,
      latencyMs,
    };
  }
}
