/**
 * Do ti le ky tu/token THAT cho tieng Viet, de chot CHARS_PER_TOKEN trong
 * src/agents/prompt/budget.ts.
 *
 * Chay TAY. Khong nam tren duong phan hoi, khong nam trong CI.
 *
 *   OPENAI_API_KEY=... node ops/calibrate-tokens.mjs
 *
 * OpenAI khong co endpoint count_tokens rieng, nen cach dem chinh xac nhat ma
 * khong them phu thuoc tokenizer la: goi that mot lan roi doc usage.prompt_tokens.
 * Ton khoang $0,01 cho ca lan chay.
 *
 * Doc ket qua: cot "ky tu/token" cang THAP thi uoc luong 3 cang an toan. Neu so do
 * that thap hon 3 dang ke (vd 2,4) thi ha CHARS_PER_TOKEN xuong. Uoc luong THAP la
 * an toan vi tha cat som con hon tran cap.
 */
import OpenAI from 'openai';
import { readFileSync } from 'node:fs';

const MODEL = 'gpt-5-mini';

// Mau tieng Viet that: co dau, co so, co ten rieng — dung loai van ban bot se gap.
const SAMPLES = {
  'hoi thoai nhom': `Chào cả nhà, cho mình hỏi deadline nộp báo cáo quý 3 là ngày nào vậy? Mình nhớ là 30/11 nhưng anh Nam bảo đã dời sang tuần sau rồi. Ai nắm rõ chỉ giúp mình với, cảm ơn mọi người nhiều.`,
  'van ban hanh chinh': `Căn cứ Quyết định số 145/QĐ-HĐQT ngày 12 tháng 8 năm 2026 về việc ban hành Quy chế chi tiêu nội bộ, các khoản công tác phí được thanh toán theo mức khoán quy định tại Phụ lục II kèm theo Quyết định này.`,
  'cau hoi ky thuat': `Mình đang cấu hình pgvector với HNSW index nhưng truy vấn vẫn chậm, khoảng 800ms cho 50 nghìn bản ghi. Có phải do chưa set ef_search không, hay là do mình dùng cosine thay vì inner product?`,
};

const client = new OpenAI();

async function countTokens(text) {
  const res = await client.chat.completions.create({
    model: MODEL,
    max_completion_tokens: 1000,
    reasoning_effort: 'low',
    messages: [{ role: 'user', content: text }],
  });
  return res.usage.prompt_tokens;
}

// Chi phi co dinh cua mot request rong — tru ra de do rieng phan van ban.
const overhead = await countTokens('.');

console.log(`Model: ${MODEL}\n`);
console.log('mau'.padEnd(24), 'ky tu'.padStart(7), 'token'.padStart(7), 'ky tu/token'.padStart(12));
console.log('-'.repeat(54));

let totalChars = 0;
let totalTokens = 0;

for (const [name, text] of Object.entries(SAMPLES)) {
  const tokens = (await countTokens(text)) - overhead;
  totalChars += text.length;
  totalTokens += tokens;
  console.log(
    name.padEnd(24),
    String(text.length).padStart(7),
    String(tokens).padStart(7),
    (text.length / tokens).toFixed(2).padStart(12),
  );
}

console.log('-'.repeat(54));
console.log(
  'TONG'.padEnd(24),
  String(totalChars).padStart(7),
  String(totalTokens).padStart(7),
  (totalChars / totalTokens).toFixed(2).padStart(12),
);

// SYSTEM_PROMPT: doc thang tu file nguon, khong bien dich TypeScript.
const src = readFileSync(new URL('../src/agents/prompt/system.ts', import.meta.url), 'utf8');
const match = /export const SYSTEM_PROMPT = `([^]*?)`;/.exec(src);
if (!match?.[1]) {
  console.error('\nKhong doc duoc SYSTEM_PROMPT tu system.ts — kiem tra lai dinh dang file.');
  process.exit(1);
}

const prompt = match[1];
const promptTokens = (await countTokens(prompt)) - overhead;

console.log(`\nSYSTEM_PROMPT: ${prompt.length} ky tu, ${promptTokens} token that`);
console.log(`Ti le: ${(prompt.length / promptTokens).toFixed(2)} ky tu/token`);
console.log(
  `Uoc luong hien tai (3 ky tu/token): ${Math.ceil(prompt.length / 3)} token — ` +
    `lech ${Math.abs(Math.ceil(prompt.length / 3) - promptTokens)} token so voi that.`,
);
