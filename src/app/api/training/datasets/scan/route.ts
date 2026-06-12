import { proxyGet } from '@/lib/proxy';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const folder = searchParams.get('folder');
  const params = folder ? `?folder=${encodeURIComponent(folder)}` : '';
  return proxyGet(request, `/api/training/datasets/scan${params}`);
}
