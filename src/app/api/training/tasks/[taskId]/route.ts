import { proxyGet } from '@/lib/proxy';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;
  return proxyGet(request, `/api/training/tasks/${taskId}`);
}
