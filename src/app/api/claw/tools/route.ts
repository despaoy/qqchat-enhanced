import { proxyGet, proxyPost } from '@/lib/proxy';

export async function GET(request: Request) {
  return proxyGet(request, '/api/claw/tools');
}

export async function POST(request: Request) {
  return proxyPost(request, '/api/claw/tools');
}
