import { proxyDelete } from '@/lib/proxy';

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string; dialogue_index: string }> }
) {
  const { id, dialogue_index } = await params;
  return proxyDelete(request, `/api/training/saved-dialogues/${id}/dialogues/${dialogue_index}`);
}
