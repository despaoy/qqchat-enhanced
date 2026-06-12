import { proxyGet } from '@/lib/proxy';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ name: string }> }
) {
  const { name } = await params;
  const response = await proxyGet(request, `/api/training/datasets/${encodeURIComponent(name)}/export`);
  if (!response.ok) {
    return new Response(JSON.stringify({ error: '导出数据集失败' }), {
      status: response.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }
  const blob = await response.blob();
  const encodedName = encodeURIComponent(name);
  return new Response(blob, {
    headers: {
      'Content-Type': 'application/zip',
      'Content-Disposition': `attachment; filename*=UTF-8''${encodedName}.zip`,
    },
  });
}
