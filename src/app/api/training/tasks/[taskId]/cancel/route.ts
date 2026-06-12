import { proxyRequest } from '@/lib/proxy';

export async function POST(
  request: Request,
  { params }: { params: Promise<{ taskId: string }> }
) {
  const { taskId } = await params;
  return proxyRequest(request, `/api/training/tasks/${taskId}/cancel`, {
    method: 'POST',
  });
}
