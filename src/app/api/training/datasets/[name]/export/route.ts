import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ name: string }> }
) {
  try {
    const { name } = await params;
    const response = await fetch(`${BACKEND_URL}/api/training/datasets/${encodeURIComponent(name)}/export`);
    if (!response.ok) {
      return NextResponse.json({ error: '导出数据集失败' }, { status: response.status });
    }
    const blob = await response.blob();
    // RFC 5987 编码文件名，支持中文
    const encodedName = encodeURIComponent(name);
    return new NextResponse(blob, {
      headers: {
        'Content-Type': 'application/zip',
        'Content-Disposition': `attachment; filename*=UTF-8''${encodedName}.zip`,
      },
    });
  } catch (error) {
    console.error('Error exporting dataset:', error);
    return NextResponse.json({ error: '导出数据集失败' }, { status: 500 });
  }
}
