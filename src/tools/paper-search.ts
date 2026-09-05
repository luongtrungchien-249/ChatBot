import type { ToolDefinition } from '../agents/ports/tool.port.js';
import { config } from '../config/index.js';
import { logger } from '../infra/logger.js';

/**
 * Tim bai bao khoa hoc tren BON nguon, chay SONG SONG roi hop nhat.
 *
 * Bon nguon bu nhau chu khong thua:
 *   OpenAlex          rong nhat (~250 trieu cong trinh), co so trich dan
 *   arXiv             preprint CS/AI/toan/vat ly, co full text PDF
 *   Semantic Scholar  co TLDR tom tat san
 *   Crossref          metadata DOI chuan nhat, nhung thuong thieu abstract
 *
 * Promise.allSettled chu khong phai Promise.all: MOT NGUON CHET KHONG DUOC LAM
 * HONG CA LOI GOI. Ba nguon con lai van du de tra loi.
 */
const TIMEOUT_MS = 15_000;
const PER_SOURCE_TIMEOUT_MS = 10_000;

export const PAPER_SEARCH_DEFINITION: ToolDefinition = {
  name: 'paper_search',
  description:
    'Tìm bài báo khoa học, công trình nghiên cứu, preprint. Dùng khi người dùng hỏi về nghiên cứu, ' +
    'papers, state of the art, hoặc muốn dẫn nguồn học thuật. Tìm đồng thời trên OpenAlex, arXiv, ' +
    'Semantic Scholar và Crossref. Truy vấn nên viết bằng TIẾNG ANH vì phần lớn công trình bằng tiếng Anh.',
  parameters: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'Từ khoá tìm kiếm, nên bằng tiếng Anh. Ví dụ: "retrieval augmented generation Vietnamese".',
      },
      max_results: {
        type: 'integer',
        description: 'Số bài cần lấy sau khi hợp nhất, từ 1 đến 15. Mặc định 8.',
        minimum: 1,
        maximum: 15,
      },
    },
    required: ['query'],
    additionalProperties: false,
  },
  requirements: {
    apiKey: 'SEMANTIC_SCHOLAR_API_KEY (tuy chon — khong co thi rate limit thap hon)',
    rateLimit: 'OpenAlex/arXiv/Crossref khong gioi han thuc te; S2 100 req/5 phut neu khong key',
    costPerCall: 'Mien phi',
    timeoutMs: TIMEOUT_MS,
  },
  returns: 'Danh sach bai bao da khu trung theo DOI, moi bai gom tieu de, nam, tac gia, DOI/URL, tom tat.',
  failureModes: [
    'Mot nguon chet -> ghi log, van tra ve ket qua cua ba nguon con lai',
    'Ca bon nguon chet -> tra ve loi, model noi la khong tra cuu duoc',
    'Truy van tieng Viet -> it ket qua; description da dan model viet tieng Anh',
  ],
};

type Paper = {
  title: string;
  year: number | null;
  doi: string | null;
  url: string | null;
  abstract: string | null;
  citations: number | null;
  source: string;
};

const clean = (s: string): string => s.replace(/\s+/g, ' ').trim();

async function getJson(url: string, headers: Record<string, string> = {}): Promise<unknown> {
  const res = await fetch(url, {
    headers: { Accept: 'application/json', ...headers },
    signal: AbortSignal.timeout(PER_SOURCE_TIMEOUT_MS),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/** OpenAlex tra abstract duoi dang inverted index: { tu: [vi tri] }. Dung lai. */
function reconstructAbstract(index: unknown): string | null {
  if (typeof index !== 'object' || index === null) return null;
  const words: string[] = [];
  for (const [word, positions] of Object.entries(index as Record<string, unknown>)) {
    if (!Array.isArray(positions)) continue;
    for (const pos of positions) {
      if (typeof pos === 'number') words[pos] = word;
    }
  }
  const text = words.filter((w) => w !== undefined).join(' ');
  return text === '' ? null : clean(text);
}

async function fromOpenAlex(query: string, n: number): Promise<Paper[]> {
  const url = `https://api.openalex.org/works?search=${encodeURIComponent(query)}&per_page=${n}`;
  const data = (await getJson(url)) as { results?: unknown[] };

  return (data.results ?? []).flatMap((raw): Paper[] => {
    const w = raw as Record<string, unknown>;
    const title = typeof w['display_name'] === 'string' ? w['display_name'] : null;
    if (title === null) return [];
    const doi = typeof w['doi'] === 'string' ? w['doi'].replace(/^https?:\/\/doi\.org\//, '') : null;
    return [
      {
        title: clean(title),
        year: typeof w['publication_year'] === 'number' ? w['publication_year'] : null,
        doi,
        url: typeof w['doi'] === 'string' ? w['doi'] : null,
        abstract: reconstructAbstract(w['abstract_inverted_index']),
        citations: typeof w['cited_by_count'] === 'number' ? w['cited_by_count'] : null,
        source: 'OpenAlex',
      },
    ];
  });
}

async function fromArxiv(query: string, n: number): Promise<Paper[]> {
  const url = `http://export.arxiv.org/api/query?search_query=all:${encodeURIComponent(query)}&max_results=${n}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(PER_SOURCE_TIMEOUT_MS) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const xml = await res.text();

  // Atom cua arXiv don gian va on dinh; khong dang keo mot parser XML vao chi de doc
  // bon truong. Neu sau nay can doc sau hon thi hay doi.
  const entries = xml.split('<entry>').slice(1);
  return entries.flatMap((entry): Paper[] => {
    const title = /<title>([\s\S]*?)<\/title>/.exec(entry)?.[1];
    if (title === undefined) return [];
    const summary = /<summary>([\s\S]*?)<\/summary>/.exec(entry)?.[1] ?? null;
    const id = /<id>([\s\S]*?)<\/id>/.exec(entry)?.[1] ?? null;
    const published = /<published>(\d{4})/.exec(entry)?.[1];
    return [
      {
        title: clean(title),
        year: published === undefined ? null : Number(published),
        doi: null,
        url: id === null ? null : clean(id),
        abstract: summary === null ? null : clean(summary),
        citations: null,
        source: 'arXiv',
      },
    ];
  });
}

async function fromSemanticScholar(query: string, n: number): Promise<Paper[]> {
  const fields = 'title,abstract,year,externalIds,citationCount,url,tldr';
  const url = `https://api.semanticscholar.org/graph/v1/paper/search?query=${encodeURIComponent(query)}&fields=${fields}&limit=${n}`;
  const headers =
    config.SEMANTIC_SCHOLAR_API_KEY === ''
      ? {}
      : { 'x-api-key': config.SEMANTIC_SCHOLAR_API_KEY };

  const data = (await getJson(url, headers)) as { data?: unknown[] };

  return (data.data ?? []).flatMap((raw): Paper[] => {
    const p = raw as Record<string, unknown>;
    const title = typeof p['title'] === 'string' ? p['title'] : null;
    if (title === null) return [];
    const ids = (p['externalIds'] ?? {}) as Record<string, unknown>;
    const tldr = (p['tldr'] ?? {}) as Record<string, unknown>;
    // TLDR ngan va sat y hon abstract — uu tien khi co.
    const summary =
      typeof tldr['text'] === 'string'
        ? tldr['text']
        : typeof p['abstract'] === 'string'
          ? p['abstract']
          : null;
    return [
      {
        title: clean(title),
        year: typeof p['year'] === 'number' ? p['year'] : null,
        doi: typeof ids['DOI'] === 'string' ? ids['DOI'] : null,
        url: typeof p['url'] === 'string' ? p['url'] : null,
        abstract: summary === null ? null : clean(summary),
        citations: typeof p['citationCount'] === 'number' ? p['citationCount'] : null,
        source: 'Semantic Scholar',
      },
    ];
  });
}

async function fromCrossref(query: string, n: number): Promise<Paper[]> {
  const url = `https://api.crossref.org/works?query=${encodeURIComponent(query)}&rows=${n}`;
  // Crossref uu tien request co lien he ("polite pool") — tra loi nhanh va on dinh hon.
  const data = (await getJson(url, { 'User-Agent': 'CP-Assistant/0.1 (mailto:admin@example.com)' })) as {
    message?: { items?: unknown[] };
  };

  return (data.message?.items ?? []).flatMap((raw): Paper[] => {
    const w = raw as Record<string, unknown>;
    const titles = w['title'];
    const title = Array.isArray(titles) && typeof titles[0] === 'string' ? titles[0] : null;
    if (title === null) return [];
    const issued = (w['issued'] ?? {}) as Record<string, unknown>;
    const parts = issued['date-parts'];
    const year =
      Array.isArray(parts) && Array.isArray(parts[0]) && typeof parts[0][0] === 'number'
        ? parts[0][0]
        : null;
    return [
      {
        title: clean(title),
        year,
        doi: typeof w['DOI'] === 'string' ? w['DOI'] : null,
        url: typeof w['URL'] === 'string' ? w['URL'] : null,
        abstract: typeof w['abstract'] === 'string' ? clean(w['abstract'].replace(/<[^>]+>/g, '')) : null,
        citations: typeof w['is-referenced-by-count'] === 'number' ? w['is-referenced-by-count'] : null,
        source: 'Crossref',
      },
    ];
  });
}

/** Khu trung theo DOI truoc, roi den tieu de chuan hoa. Giu ban co nhieu thong tin nhat. */
function merge(groups: readonly Paper[][]): Paper[] {
  const byKey = new Map<string, Paper>();

  for (const paper of groups.flat()) {
    const key =
      paper.doi !== null
        ? `doi:${paper.doi.toLowerCase()}`
        : `title:${paper.title.toLowerCase().replace(/[^a-z0-9]+/g, '')}`;

    const existing = byKey.get(key);
    if (existing === undefined) {
      byKey.set(key, paper);
      continue;
    }

    // Hop nhat: giu truong nao co gia tri, cong don ten nguon.
    byKey.set(key, {
      ...existing,
      doi: existing.doi ?? paper.doi,
      url: existing.url ?? paper.url,
      abstract: existing.abstract ?? paper.abstract,
      citations: existing.citations ?? paper.citations,
      year: existing.year ?? paper.year,
      source: existing.source.includes(paper.source)
        ? existing.source
        : `${existing.source}, ${paper.source}`,
    });
  }

  // Nhieu trich dan len truoc; bai chua co trich dan (preprint moi) xuong duoi.
  return [...byKey.values()].sort((a, b) => (b.citations ?? -1) - (a.citations ?? -1));
}

export async function runPaperSearch(
  input: Record<string, unknown>,
  traceId: string,
): Promise<string> {
  const query = typeof input['query'] === 'string' ? input['query'] : '';
  if (query.trim() === '') throw new Error('paper_search can tham so query');

  const rawMax = input['max_results'];
  const maxResults = typeof rawMax === 'number' ? Math.min(Math.max(rawMax, 1), 15) : 8;
  const perSource = Math.min(maxResults + 2, 15);

  const sources = [
    ['OpenAlex', fromOpenAlex(query, perSource)],
    ['arXiv', fromArxiv(query, perSource)],
    ['Semantic Scholar', fromSemanticScholar(query, perSource)],
    ['Crossref', fromCrossref(query, perSource)],
  ] as const;

  const settled = await Promise.allSettled(sources.map(([, p]) => p));

  const ok: Paper[][] = [];
  const failed: string[] = [];
  for (const [i, result] of settled.entries()) {
    const name = sources[i]?.[0] ?? '?';
    if (result.status === 'fulfilled') {
      ok.push(result.value);
    } else {
      failed.push(name);
      logger.warn(
        { traceId, source: name, err: String(result.reason).slice(0, 200) },
        'mot nguon paper_search that bai — van tra ve phan con lai',
      );
    }
  }

  if (ok.length === 0) throw new Error(`Ca bon nguon deu that bai: ${failed.join(', ')}`);

  const papers = merge(ok).slice(0, maxResults);
  if (papers.length === 0) return `Khong tim thay bai bao nao cho truy van "${query}".`;

  const body = papers
    .map((p, i) => {
      const bits = [
        `[${i + 1}] ${p.title}`,
        `Nam: ${p.year ?? 'khong ro'} | Trich dan: ${p.citations ?? 'khong ro'} | Nguon: ${p.source}`,
        p.doi !== null ? `DOI: ${p.doi}` : null,
        p.url !== null ? `URL: ${p.url}` : null,
        p.abstract !== null ? `Tom tat: ${p.abstract.slice(0, 700)}` : null,
      ];
      return bits.filter((b) => b !== null).join('\n');
    })
    .join('\n\n');

  const note = failed.length > 0 ? `\n\n(Luu y: khong lay duoc ket qua tu ${failed.join(', ')}.)` : '';
  return body + note;
}
