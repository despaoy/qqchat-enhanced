import { proxyRequest } from '@/lib/proxy';

export async function POST(request: Request) {
  const response = await proxyRequest(request, '/api/training/generate-dialogues/cancel', {
    method: 'POST',
  });
  if (response.status === 502 || response.status === 504) {
    return new Response(
      JSON.stringify({ success: false, message: '后端服务不可用' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
  return response;
}
