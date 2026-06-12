import { proxyRequest } from '@/lib/proxy';

export async function POST(request: Request) {
  return proxyRequest(request, '/api/knowledge/train-intent/cancel', { method: 'POST' });
}
