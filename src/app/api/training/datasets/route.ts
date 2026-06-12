import { proxyGet, proxyPost } from '@/lib/proxy';

export async function GET(request: Request) {
  return proxyGet(request, '/api/training/datasets');
}

export async function POST(request: Request) {
  return proxyPost(request, '/api/training/datasets');
}
