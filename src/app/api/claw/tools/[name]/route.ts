import { proxyDelete } from '@/lib/proxy';

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ name: string }> }
) {
  const { name } = await params;
  return proxyDelete(request, `/api/claw/tools/${name}`);
}
