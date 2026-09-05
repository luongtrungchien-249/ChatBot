import { describe, it, expect } from 'vitest';
import { chunkText, truncateAtBoundary } from '../../src/shared/chunk-text.js';

const doan = 'Cau mot rat dai o day. Cau hai cung dai khong kem.\n\nDoan sau bat dau tu day.';

describe('chunkText', () => {
  it('bat bien: ghep lai bang dung van ban goc', () => {
    for (const max of [5, 10, 17, 30, 100]) {
      expect(chunkText(doan, max).join('')).toBe(doan);
    }
  });

  it('khong chunk nao vuot maxChars', () => {
    for (const max of [5, 10, 17, 30]) {
      for (const c of chunkText(doan, max)) expect(c.length).toBeLessThanOrEqual(max);
    }
  });

  it('van ban ngan hon cap thi tra ve nguyen mot manh', () => {
    expect(chunkText('ngan', 100)).toEqual(['ngan']);
  });

  it('van ban rong tra ve mang rong', () => {
    expect(chunkText('', 100)).toEqual([]);
  });

  it('uu tien cat o ranh gioi doan van', () => {
    const [first] = chunkText(doan, 60);
    expect(first).toBe('Cau mot rat dai o day. Cau hai cung dai khong kem.\n\n');
  });

  it('khong co doan van thi cat o ranh gioi cau', () => {
    const t = 'Cau mot o day. Cau hai o day. Cau ba o day.';
    const [first] = chunkText(t, 20);
    expect(first).toBe('Cau mot o day. ');
  });

  it('khong vo tu khi con cho cat', () => {
    const t = 'alpha beta gamma delta';
    for (const max of [11, 13, 16]) {
      const chunks = chunkText(t, max);
      // Moi manh TRU MANH CUOI phai ket thuc bang khoang trang => khong cat giua tu.
      for (const c of chunks.slice(0, -1)) expect(c).toMatch(/\s$/);
    }
  });

  it('mot tu dai hon ca cap thi buoc phai cat cung', () => {
    const t = 'aaaaaaaaaaaaaaaaaaaa';
    const chunks = chunkText(t, 6);
    expect(chunks).toEqual(['aaaaaa', 'aaaaaa', 'aaaaaa', 'aa']);
    expect(chunks.join('')).toBe(t);
  });

  it('maxChars khong duong thi nem loi', () => {
    expect(() => chunkText('abc', 0)).toThrow(RangeError);
  });
});

describe('truncateAtBoundary', () => {
  it('ngan hon cap thi giu nguyen', () => {
    expect(truncateAtBoundary('ngan', 100)).toBe('ngan');
  });

  it('cat o ranh gioi va luon la tien to cua ban goc', () => {
    const kept = truncateAtBoundary(doan, 30);
    expect(kept.length).toBeLessThanOrEqual(30);
    expect(doan.startsWith(kept)).toBe(true);
  });
});
