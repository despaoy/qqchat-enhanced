import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const params = new URLSearchParams(searchParams);
    
    const response = await fetch(`${BACKEND_URL}/api/knowledge/documents?${params.toString()}`);
    if (!response.ok) {
      throw new Error('Failed to fetch knowledge documents from backend');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching knowledge documents:', error);
    return NextResponse.json(
      { error: 'Failed to fetch knowledge documents' },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/api/knowledge/documents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error('Failed to create knowledge document');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error creating knowledge document:', error);
    return NextResponse.json(
      { error: 'Failed to create knowledge document' },
      { status: 500 }
    );
  }
}
