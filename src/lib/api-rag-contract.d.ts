export interface RagCitation {
  source_title: string;
  evidence_excerpt: string;
  score: number;
  content_hash: string;
  kb_revision: string;
  section: string;
  version: string;
}

declare module "./api" {
  interface GenerateResponse {
    citations?: RagCitation[];
    confidence?: number;
    abstained?: boolean;
  }
}

export {};
