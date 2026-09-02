import { envSchema, type Env } from './schema.js';

function load(): Readonly<Env> {
  const parsed = envSchema.safeParse(process.env);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((i) => `  - ${i.path.join('.')}: ${i.message}`);
    throw new Error(`Config khong hop le:\n${issues.join('\n')}`);
  }
  return Object.freeze(parsed.data);
}

export const config = load();
