import type { ThreadScope } from '../../agents/domain/thread.js';
import type { ChannelPort } from '../../agents/ports/channel.port.js';
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
