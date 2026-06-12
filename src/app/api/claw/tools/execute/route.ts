import { proxyPost } from '@/lib/proxy';

export async function POST(request: Request) {
  return proxyPost(request, '/api/claw/tools/execute');
}
