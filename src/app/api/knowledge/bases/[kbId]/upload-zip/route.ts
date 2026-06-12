import { proxyRequest } from '@/lib/proxy';

export async function POST(request: Request, { params }: { params: Promise<{ kbId: string }> }) {
  const { kbId } = await params;
  const formData = await request.formData();
  return proxyRequest(request, `/api/knowledge/bases/${kbId}/upload-zip`, {
    method: 'POST',
    body: formData,
  });
}
