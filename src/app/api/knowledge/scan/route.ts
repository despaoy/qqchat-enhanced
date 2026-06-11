import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/api/knowledge/scan`);
    if (!response.ok) throw new Error('Failed to scan knowledge dirs');
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error scanning knowledge dirs:', error);
    return NextResponse.json({ error: 'Failed to scan knowledge dirs' }, { status: 500 });
  }
}
