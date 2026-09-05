import type { ToolDefinition } from '../agents/ports/tool.port.js';
import { config } from '../config/index.js';

/**
 * Tim kiem web qua Tavily.
 *
 * Chon Tavily vi no tra ve NOI DUNG DA TRICH XUAT san, khong chi title + snippet
 * nhu SERP thuong. Bot duoc mot vong fetch trang roi boc HTML — vong do vua cham,
 * vua la them mot be mat de dinh HTML rac vao prompt.
 */
const ENDPOINT = 'https://api.tavily.com/search';
const TIMEOUT_MS = 12_000;

export const WEB_SEARCH_DEFINITION: ToolDefinition = {
  name: 'web_search',
  description:
    'Tìm kiếm thông tin trên internet. Dùng khi câu hỏi cần thông tin thời sự, giá cả, sự kiện gần đây, ' +
    'hoặc bất cứ điều gì không có trong tài liệu nội bộ. KHÔNG dùng cho câu hỏi về quy định, quy trình ' +
    'nội bộ của tổ chức — dùng search_knowledge_base cho việc đó.',
  parameters: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'Câu truy vấn đầy đủ ngữ cảnh. Viết như đang gõ vào ô tìm kiếm.',
      },
      max_results: {
        type: 'integer',
        description: 'Số kết quả cần lấy, từ 1 đến 10. Mặc định 5.',
        minimum: 1,
        maximum: 10,
      },
    },
    required: ['query'],
    additionalProperties: false,
  },
  requirements: {
    apiKey: 'TAVILY_API_KEY',
    rateLimit: 'Goi mien phi: 1.000 luot/thang',
    costPerCall: '~$0,008 khi vuot goi mien phi',
    timeoutMs: TIMEOUT_MS,
  },
  returns: 'Danh sach ket qua, moi cai gom tieu de, URL va doan noi dung da trich xuat.',
  failureModes: [
    'Khong co TAVILY_API_KEY -> cong cu khong duoc khai trong specs()',
    'Het quota -> HTTP 429, tra ve loi, model tu noi la khong tra cuu duoc',
    'Timeout 12s -> tra ve loi, vong ReAct van tiep tuc voi cac cong cu khac',
  ],
};

type TavilyResult = { title?: string; url?: string; content?: string };
type TavilyResponse = { results?: TavilyResult[]; answer?: string };

export function isWebSearchAvailable(): boolean {
  return config.TAVILY_API_KEY !== '';
}

export async function runWebSearch(input: Record<string, unknown>): Promise<string> {
  const query = typeof input['query'] === 'string' ? input['query'] : '';
  if (query.trim() === '') throw new Error('web_search can tham so query');

  const rawMax = input['max_results'];
  const maxResults = typeof rawMax === 'number' ? Math.min(Math.max(rawMax, 1), 10) : 5;

  const res = await fetch(ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${config.TAVILY_API_KEY}`,
    },
    body: JSON.stringify({
      query,
      max_results: maxResults,
      search_depth: 'basic',
      include_answer: false, // Tu tong hop trong vong ReAct de con giu trich dan.
    }),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });

  if (!res.ok) {
    throw new Error(`Tavily tra ve ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }

  const data = (await res.json()) as TavilyResponse;
  const results = data.results ?? [];
  if (results.length === 0) return 'Khong tim thay ket qua nao cho truy van nay.';

  return results
    .map((r, i) => {
      const title = r.title ?? '(khong co tieu de)';
      const url = r.url ?? '';
      const content = (r.content ?? '').trim();
      return `[${i + 1}] ${title}\nNguon: ${url}\n${content}`;
    })
    .join('\n\n');
}
