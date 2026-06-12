import { proxyDelete } from '@/lib/proxy';

export async function DELETE(request: Request, { params }: { params: Promise<{ folderId: string }> }) {
  const { folderId } = await params;
  return proxyDelete(request, `/api/knowledge/folders/${folderId}`);
}
