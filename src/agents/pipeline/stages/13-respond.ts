import type { ThreadScope } from '../../domain/thread.js';
import type { ChannelPort } from '../../ports/channel.port.js';

/**
 * Stage 13: gui cau tra loi.
 *
 * KHONG chunk o day. Hop dong cua ChannelPort.send() la "tu chunk theo
 * maxMessageChars" — moi nen tang mot gioi han (Messenger 2000 ky tu), va agents/
 * khong duoc hardcode con so cua tung nen tang.
 */
export async function respond(
  channel: ChannelPort,
  scope: ThreadScope,
  text: string,
  replyTo?: string,
): Promise<void> {
  await channel.send(scope, text, replyTo);
}
