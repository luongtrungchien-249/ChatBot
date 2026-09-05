import pino from 'pino';
import { config } from '../config/index.js';
import { redactDeep } from '../shared/redact.js';

/**
 * L8: moi tin nhan vao co dung MOT traceId xuyen suot moi log.
 * Khong co no thi khong truy duoc mot hoi thoai hong.
 *
 * Moi tham so deu di qua redactDeep truoc khi ghi — che secret la mac dinh,
 * khong phai viec cho nguoi goi nho lam.
 */
const isDev = config.NODE_ENV === 'development';

export const logger = pino({
  level: config.LOG_LEVEL,
  base: { service: 'chien-chatbot' },
  hooks: {
    logMethod(args, method) {
      return method.apply(this, redactDeep(args));
    },
  },
  ...(isDev
    ? {
        transport: {
          target: 'pino-pretty',
          options: { colorize: true, translateTime: 'HH:MM:ss', ignore: 'pid,hostname,service' },
        },
      }
    : {}),
});

export type Logger = pino.Logger;

/** Logger cho mot tin nhan. Dung cai nay o moi stage, khong dung logger goc. */
export function childLogger(traceId: string): Logger {
  return logger.child({ traceId });
}
