import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function DELETE(request: Request, { params }: { params: Promise<{ folderId: string }> }) {
  try {
    const { folderId } = await params;
    const response = await fetch(`${BACKEND_URL}/api/knowledge/folders/${folderId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Failed to delete folder');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting folder:', error);
    return NextResponse.json({ error: 'Failed to delete folder' }, { status: 500 });
  }
}
