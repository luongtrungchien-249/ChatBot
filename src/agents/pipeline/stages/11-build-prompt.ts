import type { LoggerPort } from '../../ports/logger.port.js';
import { buildContext, type ContextEnvelope, type ContextInput } from '../../prompt/context.js';

/**
 * Stage 11: dung ngu canh theo nam vung cua so do Context Engineering.
 *
 * Toan bo logic nam o prompt/context.ts — stage nay chi la diem noi, de vung ngu
 * canh con dung duoc o cho khac (vong ReAct o stage 12 se dung lai chinh no de
 * ghep observation vao giua cac vong).
 */
export type PromptInput = ContextInput;
export type BuiltPrompt = ContextEnvelope;

export function buildPrompt(input: PromptInput, logger: LoggerPort): BuiltPrompt {
  return buildContext(input, logger);
}
