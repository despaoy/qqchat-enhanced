import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const { searchParams } = new URL(request.url);
    const datasetName = searchParams.get('dataset_name');
    let url = `${BACKEND_URL}/api/training/saved-dialogues/${id}/create-dataset`;
    if (datasetName) {
      url += `?dataset_name=${encodeURIComponent(datasetName)}`;
    }
    const response = await fetch(url, { method: 'POST' });
    const data = await response.json();
    if (!response.ok) return NextResponse.json(data, { status: response.status });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error creating dataset from saved:', error);
    return NextResponse.json({ error: '创建数据集失败' }, { status: 500 });
  }
}
