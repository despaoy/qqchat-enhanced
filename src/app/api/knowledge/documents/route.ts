import { proxyGet, proxyPost } from '@/lib/proxy';

export async function GET(request: Request) {
  return proxyGet(request, '/api/knowledge/documents?' + new URL(request.url).searchParams.toString());
}

export async function POST(request: Request) {
  return proxyPost(request, '/api/knowledge/documents');
}
