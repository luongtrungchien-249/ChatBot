/**
 * Cat van ban dai theo gioi han ky tu, uu tien ranh gioi ngu nghia.
 *
 * BAT BIEN: chunkText(t, n).join('') === t. Khong mat, khong them mot ky tu nao.
 * Cac cho goi (stage 13-respond, send.ts cua tung adapter) tu trim neu can.
 *
 * Thu tu uu tien cho cat: doan van -> dong -> cau -> tu -> cat cung.
 * Cat cung chi xay ra khi mot "tu" dai hon ca maxChars (URL, chuoi base64).
 */

/**
 * Tim vi tri cat tot nhat trong text[0..limit]. Tra ve so ky tu lay o chunk dau.
 * Ket qua LUON <= limit — cua so chi dai dung limit ky tu nen moi ung vien deu vua.
 */
function findCut(text: string, limit: number): number {
  if (text.length <= limit) return text.length;

  const window = text.slice(0, limit);

  // Doan van: lay sau dau xuong dong kep.
  const para = window.lastIndexOf('\n\n');
  if (para >= 0) return para + 2;

  // Dong.
  const line = window.lastIndexOf('\n');
  if (line >= 0) return line + 1;

  // Cau: dau cham/hoi/than roi den khoang trang.
  const sentence = /[.!?…]\s/g;
  let lastSentence = -1;
  for (let m = sentence.exec(window); m !== null; m = sentence.exec(window)) {
    lastSentence = m.index + m[0].length;
  }
  if (lastSentence > 0) return lastSentence;

  // Tu.
  const space = window.lastIndexOf(' ');
  if (space >= 0) return space + 1;

  // Mot "tu" dai hon ca cua so (URL, chuoi base64) — buoc phai cat cung.
  return limit;
}

export function chunkText(text: string, maxChars: number): string[] {
  if (maxChars <= 0) throw new RangeError('maxChars phai duong');
  if (text.length <= maxChars) return text.length === 0 ? [] : [text];

  const chunks: string[] = [];
  let rest = text;
  while (rest.length > maxChars) {
    const cut = findCut(rest, maxChars);
    chunks.push(rest.slice(0, cut));
    rest = rest.slice(cut);
  }
  if (rest.length > 0) chunks.push(rest);
  return chunks;
}

/**
 * Cat bot phan duoi, giu lai toi da maxChars ky tu dau, tai ranh gioi ngu nghia.
 * Dung boi agents/prompt/budget.ts — cat mot tang prompt cho vua cap.
 */
export function truncateAtBoundary(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text;
  return text.slice(0, findCut(text, maxChars));
}
