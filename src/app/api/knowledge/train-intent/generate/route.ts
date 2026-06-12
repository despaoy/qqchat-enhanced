import { proxyPost } from '@/lib/proxy';

export async function POST(request: Request) {
  return proxyPost(request, '/api/knowledge/train-intent/generate');
}
