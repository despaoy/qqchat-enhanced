import { proxyRequest } from '@/lib/proxy';

export async function POST(request: Request) {
  const { searchParams } = new URL(request.url);
  const directory_name = searchParams.get('directory_name');
  const kb_id = searchParams.get('kb_id');

  if (!directory_name) {
    return new Response(JSON.stringify({ error: 'directory_name is required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const params = new URLSearchParams();
  params.append('directory_name', directory_name);
  if (kb_id) params.append('kb_id', kb_id);

  return proxyRequest(request, `/api/knowledge/scan/import?${params.toString()}`, {
    method: 'POST',
  });
}
