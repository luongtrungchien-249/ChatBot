import { scopeOf, type InboundMessage } from '../../domain/message.js';
import type { ThreadScope } from '../../domain/thread.js';
import type { MemoryPort } from '../../ports/memory.port.js';

/**
 * Stage 6: ghi tin vao Postgres (nguon that), cache Redis chi la he qua.
 *
 * Ghi TRUOC khi goi model: neu model loi thi cau hoi cua nguoi dung van con trong
 * lich su. Nguoc lai se mat cau hoi moi lan API hong.
 */
export async function persistInbound(memory: MemoryPort, msg: InboundMessage): Promise<void> {
  await memory.append(scopeOf(msg), {
    messageId: msg.messageId,
    senderId: msg.senderId,
    senderName: msg.senderName,
    text: msg.text,
    isGroup: msg.isGroup,
    ...(msg.replyTo ? { replyToId: msg.replyTo.id } : {}),
    fromBot: false,
  });
}

/**
 * Ghi cau tra loi cua bot. messageId lay tu tin goc + hau to: mot cau hoi sinh ra
 * dung mot cau tra loi, nen khoa nay vua duy nhat vua tu chong trung khi job retry.
 */
export async function persistOutbound(
  memory: MemoryPort,
  scope: ThreadScope,
  inReplyToId: string,
  botName: string,
  text: string,
): Promise<void> {
  await memory.append(scope, {
    messageId: `${inReplyToId}:bot`,
    senderId: 'bot',
    senderName: botName,
    text,
    isGroup: false,
    replyToId: inReplyToId,
    fromBot: true,
  });
}
