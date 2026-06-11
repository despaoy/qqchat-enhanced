import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(request: Request, { params }: { params: Promise<{ kbId: string }> }) {
  try {
    const { kbId } = await params;
    const response = await fetch(`${BACKEND_URL}/api/knowledge/bases/${kbId}/folders`);
    if (!response.ok) throw new Error('Failed to fetch folders');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching folders:', error);
    return NextResponse.json({ error: 'Failed to fetch folders' }, { status: 500 });
  }
}

export async function POST(request: Request, { params }: { params: Promise<{ kbId: string }> }) {
  try {
    const { kbId } = await params;
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/api/knowledge/bases/${kbId}/folders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      return NextResponse.json(err, { status: response.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error creating folder:', error);
    return NextResponse.json({ error: 'Failed to create folder' }, { status: 500 });
  }
}
