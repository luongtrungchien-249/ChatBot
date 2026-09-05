import type { ThreadScope } from '../../domain/thread.js';
import type { ChannelPort } from '../../ports/channel.port.js';
import type { LoggerPort } from '../../ports/logger.port.js';

/**
 * Stage 7: bao "dang go" — KHONG await.
 *
 * Cho typing xong la them mot vong mang vao duong phan hoi de doi lay mot hieu
 * ung hinh anh. Nhung van phai .catch(): mot promise bi tu choi ma khong ai bat
 * se lam sap process o Node.
 */
export function startTyping(channel: ChannelPort, scope: ThreadScope, logger: LoggerPort): void {
  void channel.typing(scope).catch((err: unknown) => {
    logger.warn({ err: err instanceof Error ? err.message : String(err) }, 'typing that bai');
  });
}
