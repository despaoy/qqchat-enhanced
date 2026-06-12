import { proxyRequest } from '@/lib/proxy';

export async function POST(request: Request) {
  return proxyRequest(request, '/api/training/generate-dialogues/force-reset', {
    method: 'POST',
  });
}
