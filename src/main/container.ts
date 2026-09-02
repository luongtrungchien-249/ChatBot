import { config } from '../config/index.js';

/**
 * Dependency injection thu cong. Mot ham tra ve object — nhin la biet cai gi noi vao cai gi.
 * Khong dung framework DI.
 */
export async function buildContainer() {
  await assertEmbeddingDim();
  // TODO(tuan-1): khoi tao db, redis, queue, logger roi noi vao cac port.
  return {};
}

/**
 * Chan cung: so chieu model embedding phai khop cot VECTOR(n) trong DB.
 * Doc atttypmod cua cot embedding tu pg_attribute, so voi config.EMBEDDING_DIM.
 * Lech -> throw, khong cho process khoi dong.
 *
 * Khong co buoc nay, loi se hien ra duoi dang "ket qua tim kiem kem" — ba tuan sau.
 */
async function assertEmbeddingDim(): Promise<void> {
  // TODO(tuan-4): SELECT atttypmod FROM pg_attribute
  //   WHERE attrelid = 'kb_chunk'::regclass AND attname = 'embedding';
  void config.EMBEDDING_DIM;
}
