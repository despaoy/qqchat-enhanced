import { proxyRequest } from '@/lib/proxy';
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const response = await proxyRequest(request, '/api/auth/logout', {
    method: 'POST',
  });

  const data = await response.json();

  const nextResponse = NextResponse.json(data, { status: response.status });

  // Forward Set-Cookie header from backend (clears access_token)
  const setCookieHeader = response.headers.get('set-cookie');
  if (setCookieHeader) {
    nextResponse.headers.set('set-cookie', setCookieHeader);
  }

  return nextResponse;
}
