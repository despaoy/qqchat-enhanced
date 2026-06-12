import { proxyGet } from '@/lib/proxy';

export async function GET(request: Request) {
  const response = await proxyGet(request, '/health');
  if (!response.ok) {
    return new Response(
      JSON.stringify({ status: 'unhealthy', timestamp: new Date().toISOString() }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
  return response;
}
