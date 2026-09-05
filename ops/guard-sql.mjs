/**
 * L4: khong cau SQL nao duoc cham bang memory_fact ngoai src/memory/repository/.
 *
 * dependency-cruiser so khop DUONG DAN MODULE, khong doc duoc chuoi SQL — luat
 * 'memory-fact-chi-o-repository' chi chan viec IMPORT fact.repo, khong chan ai do
 * viet 'SELECT ... FROM memory_fact' thang trong knowledge/. Day la lop con thieu.
 *
 * Chay: npm run guard:sql   (bat buoc trong CI)
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, posix, sep } from 'node:path';

const ROOT = 'src';
const ALLOWED_PREFIX = 'src/memory/repository/';
const NEEDLE = 'memory_fact';

/** @param {string} dir @returns {string[]} */
function walk(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return walk(full);
    return full.endsWith('.ts') ? [full] : [];
  });
}

/**
 * Xoa comment nhung GIU nguyen so dong, de bao loi con chi dung cho.
 * Nhac ten bang trong comment la hop le; chay SQL len no thi khong.
 * @param {string} src @returns {string}
 */
function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/\/\/[^\n]*/g, '');
}

const violations = [];

for (const file of walk(ROOT)) {
  const rel = file.split(sep).join(posix.sep);
  if (rel.startsWith(ALLOWED_PREFIX)) continue;

  stripComments(readFileSync(file, 'utf8'))
    .split('\n')
    .forEach((line, i) => {
      if (line.includes(NEEDLE)) violations.push(`${rel}:${i + 1}: ${line.trim()}`);
    });
}

if (violations.length > 0) {
  console.error(
    `L4 vi pham: '${NEEDLE}' chi duoc xuat hien trong ${ALLOWED_PREFIX}\n` +
      violations.map((v) => `  ${v}`).join('\n'),
  );
  process.exit(1);
}

console.log(`guard:sql OK — khong co '${NEEDLE}' nao ngoai ${ALLOWED_PREFIX}`);
