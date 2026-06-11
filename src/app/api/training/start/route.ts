import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/api/training/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) {
      // 传递后端的实际错误信息和状态码
      const detail = data.detail || data.message || data.error || '启动训练失败';
      const errorMessage = typeof detail === 'string' ? detail : JSON.stringify(detail);
      return NextResponse.json(
        { success: false, message: errorMessage, detail: data.detail },
        { status: response.status }
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error starting training:', error);
    return NextResponse.json(
      { success: false, message: '无法连接到训练服务' },
      { status: 500 }
    );
  }
}
