import type { BotError } from '../../domain/errors.js';
import type { CallContext, LlmPort } from '../../ports/llm.port.js';
import type { LoggerPort } from '../../ports/logger.port.js';
import { err, ok, type Result } from '../../../shared/result.js';
import type { BuiltPrompt } from './11-build-prompt.js';

/**
 * Stage 12: goi model.
 *
 * O giai doan 2, day la cho vong ReAct thay the mot lan goi don le. Moi thu quanh
 * no (policy, ngan sach, chong trung, thu tu) van o cac stage khac.
 *
 * Timeout va fallback: IM LANG trong nhom trong nhu bot chet, va nguoi dung se
 * spam mention. Tha tra mot cau ngan con hon khong tra gi.
 */
/** Loi tam thoi: cham, 5xx, mat mang. Thu lai THAT SU co the giup. */
export const FALLBACK_TEXT =
  'Xin lỗi, mình đang bị chậm nên chưa trả lời được câu này. Bạn thử hỏi lại sau một chút nhé.';

/**
 * Loi cau hinh (khoa sai/het han). Bao thu lai la NOI DOI: thu bao nhieu lan cung
 * hong cho toi khi co nguoi sua bien moi truong.
 *
 * Khong noi ro "sai API key" trong nhom chat — do la thong tin van hanh, chi thuoc
 * ve log. Nguoi dung chi can biet loi khong nam o phia ho.
 */
export const CONFIG_ERROR_TEXT =
  'Mình đang gặp trục trặc kỹ thuật ở phía hệ thống, chưa trả lời được. Bạn báo giúp người quản trị nhé.';

/** Doc HTTP status tu loi cua SDK ma khong phai import SDK (L1: agents khong biet llm). */
function statusOf(err: unknown): number | undefined {
  if (typeof err === 'object' && err !== null && 'status' in err) {
    const { status } = err as { status: unknown };
    if (typeof status === 'number') return status;
  }
  return undefined;
}

export type GenerateDeps = Readonly<{
  llm: LlmPort;
  maxTokens: number;
  effort: 'low' | 'medium' | 'high';
}>;

export async function generate(
  deps: GenerateDeps,
  prompt: BuiltPrompt,
  ctx: CallContext,
  logger: LoggerPort,
): Promise<Result<string, BotError>> {
  try {
    const res = await deps.llm.reply({
      system: prompt.system,
      messages: prompt.messages,
      maxTokens: deps.maxTokens,
      effort: deps.effort,
      ctx,
    });

    // Model reasoning co the tieu het cap cho phan suy luan roi tra ve chuoi rong.
    // llm/openai.client.ts da log chi tiet; o day chi can khong gui tin rong di.
    if (res.text.trim() === '') {
      logger.error({ usage: res.usage }, 'model tra ve chuoi rong');
      return err({ kind: 'upstream_error', service: 'llm' });
    }

    return ok(res.text);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    const status = statusOf(e);

    if (status === 401 || status === 403) {
      // Loi cua NGUOI VAN HANH, khong phai cua nguoi dung. Log to len: khong co
      // dong nay thi trieu chung o phia nguoi dung ('bot khong hieu gi ca') khong
      // he chi ve nguyen nhan that (OPENAI_API_KEY sai hoac het han).
      logger.error({ status, err: message }, 'API key sai hoac het quyen — KIEM TRA OPENAI_API_KEY');
    } else {
      logger.error({ status, err: message }, 'goi model that bai');
    }

    // Timeout KHONG retry: nguoi dung da nhan cau fallback roi.
    // Cac truong hop con lai de isRetryable() trong domain/errors.ts quyet dinh
    // theo status — 401 khong duoc retry, 429/5xx thi duoc.
    const isTimeout = /timeout|aborted|ETIMEDOUT/i.test(message);
    if (isTimeout) return err({ kind: 'upstream_timeout', service: 'llm' });

    return err({
      kind: 'upstream_error',
      service: 'llm',
      ...(status === undefined ? {} : { status }),
    });
  }
}
