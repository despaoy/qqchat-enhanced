import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/knowledge/bases`);
    if (!response.ok) throw new Error('Failed to fetch knowledge bases');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching knowledge bases:', error);
    return NextResponse.json({ error: 'Failed to fetch knowledge bases' }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/api/knowledge/bases`, {
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
    console.error('Error creating knowledge base:', error);
    return NextResponse.json({ error: 'Failed to create knowledge base' }, { status: 500 });
  }
}
