import { describe, it, expect } from 'vitest';
import { redact, redactDeep } from '../../src/shared/redact.js';

describe('redact', () => {
  it('che API key ho sk- cua moi nha cung cap', () => {
    for (const key of [
      'sk-proj-AbCdEf123456_xyz-QQrstu',
      'sk-svcacct-AbCdEf123456xyzQQ',
      'sk-ant-api03-AbCdEf123456_xyz-QQ',
      'sk-AbCdEf123456xyzQQrstu',
    ]) {
      const out = redact(`key la ${key} nhe`);
      expect(out, key).toBe('key la sk-*** nhe');
    }
  });

  it('che key Tavily', () => {
    expect(redact('TAVILY_API_KEY=tvly-AbCdEf123456xyz')).toBe('TAVILY_API_KEY=tvly-***');
  });

  it('che token Zalo dang numeric_id:secret', () => {
    const out = redact('ZALO_BOT_TOKEN=1234567890:AbCdEfGhIjKlMnOpQr');
    expect(out).not.toContain('AbCdEfGhIjKlMnOpQr');
    expect(out).toContain('***:***');
  });

  it('che page token cua Meta', () => {
    const out = redact('token EAAGm0PX4ZCpsBAxxxxxxxxxxxxxxxxxxxxx het');
    expect(out).not.toContain('EAAGm0PX4ZCpsBAxxxx');
    expect(out).toContain('EAA***');
  });

  it('che mat khau trong chuoi ket noi', () => {
    const out = redact('postgres://bot:sieubimat@localhost:5432/chatbot');
    expect(out).not.toContain('sieubimat');
    expect(out).toBe('postgres://***:***@localhost:5432/chatbot');
  });

  it('che so dien thoai Viet Nam, ca hai dang', () => {
    expect(redact('goi 0912345678 di')).toBe('goi *** di');
    expect(redact('hoac +84912345678')).toBe('hoac ***');
  });

  it('che email nhung giu ten mien de con debug duoc', () => {
    expect(redact('lien he nam.tran@congty.vn nhe')).toBe('lien he ***@congty.vn nhe');
  });

  it('che header uy quyen', () => {
    expect(redact('Authorization: Bearer abc123def456ghi')).toBe('Authorization: Bearer ***');
  });

  it('khong dung toi van ban thuong', () => {
    const t = 'Deadline la 30/11, hop luc 14h tai phong 302.';
    expect(redact(t)).toBe(t);
  });

  it('khong an nham ma san pham nhin giong so dien thoai', () => {
    // 8 chu so, khong phai 10 -> khong phai so dien thoai VN.
    expect(redact('ma don hang 01234567')).toBe('ma don hang 01234567');
  });
});

describe('redactDeep', () => {
  it('di vao object long nhau va giu nguyen hinh dang', () => {
    const input = {
      traceId: 'tr1',
      user: { phone: '0912345678', email: 'a@b.vn' },
      tags: ['sk-ant-api03-SECRETSECRET', 'binh thuong'],
      count: 3,
      ok: true,
      nothing: null,
    };
    expect(redactDeep(input)).toEqual({
      traceId: 'tr1',
      user: { phone: '***', email: '***@b.vn' },
      tags: ['sk-***', 'binh thuong'],
      count: 3,
      ok: true,
      nothing: null,
    });
  });
});
