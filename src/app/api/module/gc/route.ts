import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST() {
  const res = await fetch(`${BACKEND_URL}/api/module/gc`, { method: 'POST' });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
