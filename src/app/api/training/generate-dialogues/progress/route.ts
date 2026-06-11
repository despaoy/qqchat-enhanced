import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/training/generate-dialogues/progress`);
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({
      is_generating: false,
      progress: 0,
      total: 0,
      batch_num: 0,
      total_batches: 0,
      generated_count: 0,
    }, { status: 503 });
  }
}
