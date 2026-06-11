import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { directory_name, kb_id } = body;
    const params = new URLSearchParams();
    params.append('directory_name', directory_name);
    if (kb_id) params.append('kb_id', kb_id.toString());

    const response = await fetch(`${BACKEND_URL}/api/knowledge/scan/import?${params.toString()}`, {
      method: 'POST',
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      return NextResponse.json(err, { status: response.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error importing scanned directory:', error);
    return NextResponse.json({ error: 'Failed to import scanned directory' }, { status: 500 });
  }
}
