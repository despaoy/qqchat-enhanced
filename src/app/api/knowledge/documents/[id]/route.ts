import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const response = await fetch(`${BACKEND_URL}/api/knowledge/documents/${id}`);
    if (!response.ok) {
      throw new Error('Failed to fetch knowledge document from backend');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching knowledge document:', error);
    return NextResponse.json(
      { error: 'Failed to fetch knowledge document' },
      { status: 500 }
    );
  }
}

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/api/knowledge/documents/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error('Failed to update knowledge document');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error updating knowledge document:', error);
    return NextResponse.json(
      { error: 'Failed to update knowledge document' },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const response = await fetch(`${BACKEND_URL}/api/knowledge/documents/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete knowledge document');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting knowledge document:', error);
    return NextResponse.json(
      { error: 'Failed to delete knowledge document' },
      { status: 500 }
    );
  }
}
