import { proxyPost } from '@/lib/proxy';
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const response = await proxyPost(request, '/api/training/start');
  if (!response.ok) {
    const data = await response.json();
    const detail = data.detail || data.message || data.error || '启动训练失败';
    const errorMessage = typeof detail === 'string' ? detail : JSON.stringify(detail);
    return NextResponse.json(
      { success: false, message: errorMessage, detail: data.detail },
      { status: response.status }
    );
  }
  return response;
}
