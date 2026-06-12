import { proxyRequest } from '@/lib/proxy';

export async function DELETE(request: Request) {
  const body = await request.json();
  return proxyRequest(request, '/api/messages/batch', {
    method: 'DELETE',
    body,
    headers: { 'Content-Type': 'application/json' },
  });
}
