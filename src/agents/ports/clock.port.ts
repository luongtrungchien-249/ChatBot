/** Co port cho thoi gian de test xac dinh duoc. Khong goi Date.now() trong agents/. */
export interface ClockPort {
  now(): Date;
}
