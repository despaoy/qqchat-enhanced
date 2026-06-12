import { proxyGet } from '@/lib/proxy';

export async function GET(request: Request) {
  const response = await proxyGet(request, '/api/training/generate-dialogues/progress');
  if (response.status === 502 || response.status === 504) {
    return new Response(
      JSON.stringify({
        is_generating: false,
        progress: 0,
        total: 0,
        batch_num: 0,
        total_batches: 0,
        generated_count: 0,
      }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
  return response;
}
