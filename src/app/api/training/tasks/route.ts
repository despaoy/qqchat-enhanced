import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/training/tasks`);
    if (!response.ok) {
      throw new Error('Failed to fetch training tasks from backend');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching training tasks:', error);
    return NextResponse.json(
      { error: 'Failed to fetch training tasks' },
      { status: 500 }
    );
  }
}
