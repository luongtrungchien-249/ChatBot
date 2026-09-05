import type { CallContext, ToolCall, ToolSpec } from './llm.port.js';

/**
 * Cong cu ma agent duoc phep goi.
 *
 * tools/ goi mang ra ngoai nen la HA TANG (L1) — agents/ chi thay no qua port nay.
 * Luat 'agents-khong-biet-ha-tang' trong .dependency-cruiser.cjs cuong che dieu do.
 *
 * ToolDefinition mo ta NHIEU hon ToolSpec ma API can. Phan thua (requirements,
 * failureModes) khong gui len model — no o day de nguoi doc code biet cong cu nay
 * can khoa gi, ton bao nhieu, va hong theo kieu nao, ma khong phai mo tung file
 * implementation ra doc.
 */
export type JsonSchema = Readonly<Record<string, unknown>>;

export type ToolRequirements = Readonly<{
  /** TEN bien moi truong, khong phai gia tri. Khong co = khong can khoa. */
  apiKey?: string;
  rateLimit: string;
  costPerCall: string;
  timeoutMs: number;
}>;

export type ToolDefinition = Readonly<{
  name: string;
  /** Model doc dong nay de chon cong cu. Viet cho MODEL doc, khong phai cho nguoi. */
  description: string;
  parameters: JsonSchema;
  requirements: ToolRequirements;
  returns: string;
  failureModes: readonly string[];
}>;

export type ToolResult = Readonly<{
  /** Khop voi ToolCall.id. Thieu mot cai la ca request 400. */
  toolCallId: string;
  name: string;
  /** Van ban dua vao prompt. Da duoc boc the va cat theo tran tang 'tool'. */
  content: string;
  ok: boolean;
  /** Cong cu chay het bao lau — de biet cong cu nao dang keo p95 len. */
  latencyMs: number;
}>;

export interface ToolPort {
  /**
   * Cong cu dang thuc su dung duoc. Thieu khoa API thi KHONG khai o day —
   * de model thay mot cong cu roi goi that bai la cach nhanh nhat de no bia ra
   * ket qua.
   */
  specs(): readonly ToolDefinition[];

  /**
   * callMany chu khong phai call: model tra nhieu tool_call trong MOT message, va
   * chung phai chay dong thoi. Tra ve DU so ket qua, ke ca cai that bai — thieu
   * mot toolCallId la API 400.
   */
  callMany(calls: readonly ToolCall[], ctx: CallContext): Promise<readonly ToolResult[]>;
}

/** Chuyen ToolDefinition sang dang API nhan. Phan requirements khong gui len model. */
export function toSpec(def: ToolDefinition): ToolSpec {
  return { name: def.name, description: def.description, inputSchema: def.parameters };
}
