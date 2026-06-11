import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/training/styles`);
    if (!response.ok) {
      throw new Error('Failed to fetch styles from backend');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching styles:', error);
    return NextResponse.json(
      { error: 'Failed to fetch styles' },
      { status: 500 }
    );
  }
}
