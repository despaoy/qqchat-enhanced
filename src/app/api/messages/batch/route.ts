import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function DELETE(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/api/messages/batch`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error('Failed to delete messages batch from backend');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting messages batch:', error);
    return NextResponse.json(
      { error: 'Failed to delete messages batch' },
      { status: 500 }
    );
  }
}
