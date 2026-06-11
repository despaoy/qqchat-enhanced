import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function PUT(request: Request, { params }: { params: Promise<{ kbId: string }> }) {
  try {
    const { kbId } = await params;
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/api/knowledge/bases/${kbId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error('Failed to update knowledge base');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error updating knowledge base:', error);
    return NextResponse.json({ error: 'Failed to update knowledge base' }, { status: 500 });
  }
}

export async function DELETE(request: Request, { params }: { params: Promise<{ kbId: string }> }) {
  try {
    const { kbId } = await params;
    const response = await fetch(`${BACKEND_URL}/api/knowledge/bases/${kbId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Failed to delete knowledge base');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting knowledge base:', error);
    return NextResponse.json({ error: 'Failed to delete knowledge base' }, { status: 500 });
  }
}
