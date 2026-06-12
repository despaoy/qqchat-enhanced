import { proxyGet, proxyPut } from '@/lib/proxy';

export async function GET(request: Request) {
  const qs = new URL(request.url).searchParams.toString();
  return proxyGet(request, `/api/user/data${qs ? '?' + qs : ''}`);
}

export async function PUT(request: Request) {
  return proxyPut(request, '/api/user/data');
}
