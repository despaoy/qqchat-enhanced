import { proxyPost } from '@/lib/proxy';
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const response = await proxyPost(request, '/api/auth/register');

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    data = { detail: '服务器返回了非 JSON 响应' };
  }

  const nextResponse = NextResponse.json(data, { status: response.status });

  // Forward Set-Cookie header from backend (httpOnly access_token)
  const setCookieHeader = response.headers.get('set-cookie');
  if (setCookieHeader) {
    nextResponse.headers.set('set-cookie', setCookieHeader);
  }

  return nextResponse;
}
