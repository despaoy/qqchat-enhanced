import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(request: Request) {
  try {
    const authHeader = request.headers.get('Authorization') || '';
    const response = await fetch(`${BACKEND_URL}/api/auth/me`, {
      headers: { 'Authorization': authHeader },
    });
    const data = await response.json();
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching user:', error);
    return NextResponse.json({ error: '获取用户信息失败' }, { status: 500 });
  }
}
