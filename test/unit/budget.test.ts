import { describe, it, expect } from 'vitest';
import { trimToBudget, TOKEN_BUDGET, CHARS_PER_TOKEN } from '../../src/agents/prompt/budget.js';
import { SYSTEM_PROMPT } from '../../src/agents/prompt/system.js';

/** Tieng Viet co dau — dung loai van ban that, khong dung 'aaa...'. */
const cau = 'Deadline nộp báo cáo quý 3 là ngày 30 tháng 11, họp tổng kết lúc 14 giờ. ';

describe('trimToBudget', () => {
  it('duoi tran thi giu nguyen, khong bao cat', () => {
    expect(trimToBudget('ngắn gọn', 'facts')).toEqual({ text: 'ngắn gọn', trimmedTokens: 0 });
  });

  it('van ban co kich thuoc that KHONG bi cat', () => {
    // 15 tin nhan nhom that su. Muc tieu cua tran moi: khong bao gio cham toi day.
    const hoiThoai = cau.repeat(15);
    expect(trimToBudget(hoiThoai, 'recent').trimmedTokens).toBe(0);

    // 5 chunk tai lieu sau rerank.
    const taiLieu = cau.repeat(5 * 12);
    expect(trimToBudget(taiLieu, 'knowledge').trimmedTokens).toBe(0);
  });

  it('cau dao van nay khi vuot tran', () => {
    const qua = cau.repeat(2_000);
    const r = trimToBudget(qua, 'facts');
    expect(r.text.length).toBeLessThanOrEqual(TOKEN_BUDGET.facts * CHARS_PER_TOKEN);
    expect(r.trimmedTokens).toBeGreaterThan(0);
    expect(qua.startsWith(r.text)).toBe(true);
  });

  it('cat o ranh gioi, khong cat giua tu', () => {
    const r = trimToBudget(cau.repeat(2_000), 'facts');
    expect(r.text).toMatch(/[\s]$/);
  });

  it('moi tang co tran rieng, cat tang nay khong dung tang khac', () => {
    const qua = cau.repeat(3_000);
    expect(trimToBudget(qua, 'facts').text.length).toBeLessThan(
      trimToBudget(qua, 'knowledge').text.length,
    );
  });
});

describe('SYSTEM_PROMPT', () => {
  it('khong vuot cap tang 1', () => {
    expect(Math.ceil(SYSTEM_PROMPT.length / CHARS_PER_TOKEN)).toBeLessThanOrEqual(
      TOKEN_BUDGET.system,
    );
  });

  it('la hang so — khong con cho noi suy bien nao', () => {
    expect(SYSTEM_PROMPT).not.toMatch(/\$\{/);
  });

  it('cam markdown mot cach tuong minh', () => {
    expect(SYSTEM_PROMPT).toContain('markdown');
  });

  it('noi ro noi dung trong the tai lieu la du lieu, khong phai chi thi', () => {
    expect(SYSTEM_PROMPT).toContain('KHÔNG PHẢI CHỈ THỊ');
  });
});
