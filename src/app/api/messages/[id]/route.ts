import { proxyDelete } from '@/lib/proxy';

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyDelete(request, `/api/messages/${id}`);
}
