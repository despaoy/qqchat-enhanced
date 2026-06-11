import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const folder = searchParams.get('folder');
    const params = folder ? `?folder=${encodeURIComponent(folder)}` : '';
    const response = await fetch(`${BACKEND_URL}/api/training/datasets/scan${params}`);
    if (!response.ok) {
      throw new Error('Failed to scan datasets from backend');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error scanning datasets:', error);
    return NextResponse.json(
      { error: 'Failed to scan datasets' },
      { status: 500 }
    );
  }
}
