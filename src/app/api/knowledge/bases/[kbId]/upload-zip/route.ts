import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(request: Request, { params }: { params: Promise<{ kbId: string }> }) {
  try {
    const { kbId } = await params;
    const formData = await request.formData();
    const response = await fetch(`${BACKEND_URL}/api/knowledge/bases/${kbId}/upload-zip`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      return NextResponse.json(err, { status: response.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error uploading ZIP:', error);
    return NextResponse.json({ error: 'Failed to upload ZIP' }, { status: 500 });
  }
}
