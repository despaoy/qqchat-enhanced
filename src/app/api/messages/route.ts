import { proxyGet } from '@/lib/proxy';

export async function GET(request: Request) {
  return proxyGet(request, '/api/messages?' + new URL(request.url).searchParams.toString());
}
