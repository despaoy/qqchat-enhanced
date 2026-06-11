import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string; dialogue_index: string }> }
) {
  try {
    const { id, dialogue_index } = await params;
    const response = await fetch(`${BACKEND_URL}/api/training/saved-dialogues/${id}/dialogues/${dialogue_index}`, {
      method: 'DELETE',
    });
    const data = await response.json();
    if (!response.ok) return NextResponse.json(data, { status: response.status });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting dialogue:', error);
    return NextResponse.json({ error: '删除失败' }, { status: 500 });
  }
}
