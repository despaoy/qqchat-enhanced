import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/api/knowledge/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error('Failed to search knowledge');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error searching knowledge:', error);
    return NextResponse.json(
      { error: 'Failed to search knowledge' },
      { status: 500 }
    );
  }
}
