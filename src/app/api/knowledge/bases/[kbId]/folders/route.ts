import { proxyGet, proxyPost } from '@/lib/proxy';

export async function GET(request: Request, { params }: { params: Promise<{ kbId: string }> }) {
  const { kbId } = await params;
  return proxyGet(request, `/api/knowledge/bases/${kbId}/folders`);
}

export async function POST(request: Request, { params }: { params: Promise<{ kbId: string }> }) {
  const { kbId } = await params;
  return proxyPost(request, `/api/knowledge/bases/${kbId}/folders`);
}
