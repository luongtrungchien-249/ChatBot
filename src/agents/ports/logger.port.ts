/**
 * L8: moi tin nhan vao co dung MOT traceId xuyen suot moi log.
 *
 * agents/ khong duoc import infra/ nen phai co port rieng. Interface nay khop
 * cau truc voi pino.Logger, nen infra/logger.ts cam thang vao, khong can adapter.
 *
 * Logger truyen vao stage LUON la child logger da gan traceId — stage khong tu
 * gan lay, va cung khong the quen.
 */
export interface LoggerPort {
  debug(obj: object, msg?: string): void;
  info(obj: object, msg?: string): void;
  warn(obj: object, msg?: string): void;
  error(obj: object, msg?: string): void;
  /** Gan them truong co dinh (traceId) — pino.Logger.child() khop san chu ky nay. */
  child(bindings: object): LoggerPort;
}
