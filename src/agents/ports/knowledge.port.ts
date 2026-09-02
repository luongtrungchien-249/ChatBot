export type RetrievedChunk = Readonly<{
  chunkId: string;
  docTitle: string;
  section: string | null;
  page: number | null;
  content: string;
  score: number;
}>;

export interface KnowledgePort {
  /** Da fusion + rerank + loc nguong RERANK_MIN_SCORE. Rong = "khong tim thay trong tai lieu". */
  search(query: string, k: number): Promise<RetrievedChunk[]>;
}
