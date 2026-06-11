import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/training/generate-dialogues/cancel`, {
      method: 'POST',
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ success: false, message: '后端服务不可用' }, { status: 503 });
  }
}
