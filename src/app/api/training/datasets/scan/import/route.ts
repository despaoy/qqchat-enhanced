import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await fetch(`${BACKEND_URL}/api/training/datasets/scan/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error('Failed to import dataset from backend');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error importing dataset:', error);
    return NextResponse.json(
      { error: 'Failed to import dataset' },
      { status: 500 }
    );
  }
}
