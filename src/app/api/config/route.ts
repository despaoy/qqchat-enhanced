import { proxyGet, proxyPut } from '@/lib/proxy';

export async function GET(request: Request) {
  return proxyGet(request, '/api/config');
}

export async function PUT(request: Request) {
  return proxyPut(request, '/api/config');
}
