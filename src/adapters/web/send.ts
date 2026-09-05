import type { ThreadScope } from '../../agents/domain/thread.js';
import type { ChannelPort } from '../../agents/ports/channel.port.js';
import { logger } from '../../infra/logger.js';
import { redis } from '../../infra/redis.js';
import { WEB_MAX_MESSAGE_CHARS, webChannelKey, type WebEvent } from './normalize.js';

/**
 * ChannelPort cua web: PUBLISH len Redis, process `api` doc lai roi day xuong SSE.
 *
 * Worker va api la hai process khac nhau — day la duong duy nhat noi chung. Cung
 * la ly do web van di qua hang doi nhu moi adapter khac (L5) thay vi goi thang.
 */
async function publish(threadId: string, event: WebEvent): Promise<void> {
  await redis.publish(webChannelKey(threadId), JSON.stringify(event));
}

/**
 * Day su kien tien do (ReAct) xuong UI.
 *
 * KHONG await o cho goi: bao tien do khong duoc chan duong tra loi. Loi o day chi
 * lam mat mot dong hien thi, khong duoc lam hong ca luot.
 */
export function publishProgress(threadId: string, event: WebEvent): void {
  void publish(threadId, event).catch((err: unknown) => {
    logger.warn(
      { threadId, err: err instanceof Error ? err.message : String(err) },
      'khong day duoc su kien tien do',
    );
  });
}

export const webChannel: ChannelPort = {
  // Web khong co gioi han that su nhu Messenger; de rong de khong cat cau tra loi.
  maxMessageChars: WEB_MAX_MESSAGE_CHARS,

  async typing(scope: ThreadScope): Promise<void> {
    await publish(scope.threadId, { type: 'typing' });
  },

  async send(scope: ThreadScope, text: string): Promise<void> {
    await publish(scope.threadId, { type: 'final', text });
  },
};
