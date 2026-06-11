import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/training/generate-dialogues/force-reset`, {
      method: 'POST',
    });
    const data = await response.json();
    if (!response.ok) return NextResponse.json(data, { status: response.status });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error force resetting:', error);
    return NextResponse.json({ error: '重置失败' }, { status: 500 });
  }
}
