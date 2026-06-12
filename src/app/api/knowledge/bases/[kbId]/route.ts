import { proxyPut, proxyDelete } from '@/lib/proxy';

export async function PUT(request: Request, { params }: { params: Promise<{ kbId: string }> }) {
  const { kbId } = await params;
  return proxyPut(request, `/api/knowledge/bases/${kbId}`);
}

export async function DELETE(request: Request, { params }: { params: Promise<{ kbId: string }> }) {
  const { kbId } = await params;
  return proxyDelete(request, `/api/knowledge/bases/${kbId}`);
}
