import { proxyRequest } from '@/lib/proxy';

export async function DELETE(request: Request) {
  // 容错：DELETE 可能不带 body 或非 JSON，避免 .json() 抛错导致 500
  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  return proxyRequest(request, '/api/messages/batch', {
    method: 'DELETE',
    body,
    headers: { 'Content-Type': 'application/json' },
  });
}
