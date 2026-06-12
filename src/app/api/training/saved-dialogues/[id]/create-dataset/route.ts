import { proxyRequest } from '@/lib/proxy';

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const { searchParams } = new URL(request.url);
  const datasetName = searchParams.get('dataset_name');
  let path = `/api/training/saved-dialogues/${id}/create-dataset`;
  if (datasetName) {
    path += `?dataset_name=${encodeURIComponent(datasetName)}`;
  }
  return proxyRequest(request, path, { method: 'POST' });
}
