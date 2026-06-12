import { proxyGet, proxyDelete } from '@/lib/proxy';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyGet(request, `/api/training/saved-dialogues/${id}`);
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyDelete(request, `/api/training/saved-dialogues/${id}`);
}
