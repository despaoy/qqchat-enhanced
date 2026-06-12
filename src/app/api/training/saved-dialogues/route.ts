import { proxyGet, proxyPost } from '@/lib/proxy';

export async function GET(request: Request) {
  return proxyGet(request, '/api/training/saved-dialogues');
}

export async function POST(request: Request) {
  return proxyPost(request, '/api/training/saved-dialogues');
}
