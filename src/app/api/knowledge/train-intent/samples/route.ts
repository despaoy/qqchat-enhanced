import { proxyGet, proxyPost, proxyPut, proxyPatch, proxyRequest } from '@/lib/proxy';

export async function GET(request: Request) {
  return proxyGet(request, '/api/knowledge/train-intent/samples');
}

export async function POST(request: Request) {
  return proxyPost(request, '/api/knowledge/train-intent/samples');
}

export async function PUT(request: Request) {
  return proxyPut(request, '/api/knowledge/train-intent/samples');
}

export async function PATCH(request: Request) {
  return proxyPatch(request, '/api/knowledge/train-intent/samples');
}

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url);
  const label = searchParams.get('label');
  const index = searchParams.get('index');
  return proxyRequest(request, `/api/knowledge/train-intent/samples?label=${encodeURIComponent(label || '')}&index=${index}`, {
    method: 'DELETE',
  });
}
