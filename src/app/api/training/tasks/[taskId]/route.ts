import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ taskId: string }> }
) {
  try {
    const { taskId } = await params;
    const response = await fetch(`${BACKEND_URL}/api/training/tasks/${taskId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch training task from backend');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching training task:', error);
    return NextResponse.json(
      { error: 'Failed to fetch training task' },
      { status: 500 }
    );
  }
}
