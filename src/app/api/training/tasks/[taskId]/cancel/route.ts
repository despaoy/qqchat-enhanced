import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(
  request: Request,
  { params }: { params: Promise<{ taskId: string }> }
) {
  try {
    const { taskId } = await params;
    const response = await fetch(`${BACKEND_URL}/api/training/tasks/${taskId}/cancel`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to cancel training task');
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error cancelling training task:', error);
    return NextResponse.json(
      { error: 'Failed to cancel training task' },
      { status: 500 }
    );
  }
}
