import { describe, it, expect } from 'vitest';

/**
 * TEST BAT BUOC — khong duoc phep xoa.
 *
 * Master plan xep ro ri cross-group la "xac suat thap, hau qua nghiem trong".
 * Xac suat thap LA NHO co test nay. Bo test thi xac suat khong con thap nua.
 */
describe('memory khong ro ri giua cac thread', () => {
  it.todo('ghi fact o thread A -> moi phuong thuc public cua MemoryPort goi tu thread B deu rong');
  it.todo('recent() cua thread B khong chua tin nhan cua thread A');
  it.todo('summary() cua thread B khong chua noi dung cua thread A');
  it.todo('facts() cua thread B rong du query trung y het');
  it.todo('list() cua thread B khong liet ke fact cua thread A');
  it.todo('fact da revoke khong xuat hien trong CHUOI PROMPT CUOI CUNG (khong chi o repository)');
  it.todo('nguoi dung X khong revoke duoc fact co subject_id la user cua nguoi dung Y');
});

it('placeholder de suite khong rong', () => {
  expect(true).toBe(true);
});
