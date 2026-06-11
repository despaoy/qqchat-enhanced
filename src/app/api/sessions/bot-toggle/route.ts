import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function PUT(request: Request) {
  try {
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/api/sessions/bot-toggle`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error('Failed to toggle session bot');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error toggling session bot:', error);
    return NextResponse.json(
      { error: 'Failed to toggle session bot' },
      { status: 500 }
    );
  }
}
