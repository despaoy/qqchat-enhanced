import { proxyPut } from '@/lib/proxy';

export async function PUT(request: Request) {
  return proxyPut(request, '/api/sessions/bot-toggle');
}
