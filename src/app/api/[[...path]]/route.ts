import { proxyRequest } from '@/lib/proxy';

type RouteContext = { params: Promise<{ path?: string[] }> };

function buildPath(segments: string[], search: string): string {
  const base = segments.length > 0 ? `/api/${segments.join('/')}` : '';
  return search ? `${base}?${search}` : base;
}

async function parseJsonBody(request: Request): Promise<{ ok: true; data: unknown } | { ok: false; response: Response }> {
  try {
    const text = await request.text();
    const data = JSON.parse(text);
    return { ok: true, data };
  } catch {
    return {
      ok: false,
      response: Response.json({ detail: '请求体不是有效的 JSON' }, { status: 400 }),
    };
  }
}

export async function GET(request: Request, { params }: RouteContext) {
  const { path } = await params;
  const segments = path || [];
  if (segments.length === 0) {
    return Response.json({ error: 'Not Found' }, { status: 404 });
  }
  const { searchParams } = new URL(request.url);
  const backendPath = buildPath(segments, searchParams.toString());
  return proxyRequest(request, backendPath);
}

export async function POST(request: Request, { params }: RouteContext) {
  const { path } = await params;
  const segments = path || [];
  if (segments.length === 0) {
    return Response.json({ error: 'Not Found' }, { status: 404 });
  }
  const { searchParams } = new URL(request.url);
  const backendPath = buildPath(segments, searchParams.toString());

  const contentType = request.headers.get('Content-Type') || '';
  if (contentType.includes('multipart/form-data')) {
    const formData = await request.formData();
    return proxyRequest(request, backendPath, {
      method: 'POST',
      body: formData,
    });
  }

  const parsed = await parseJsonBody(request);
  if (!parsed.ok) return parsed.response;
  return proxyRequest(request, backendPath, {
    method: 'POST',
    body: parsed.data,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function PUT(request: Request, { params }: RouteContext) {
  const { path } = await params;
  const segments = path || [];
  if (segments.length === 0) {
    return Response.json({ error: 'Not Found' }, { status: 404 });
  }
  const { searchParams } = new URL(request.url);
  const backendPath = buildPath(segments, searchParams.toString());
  const parsed = await parseJsonBody(request);
  if (!parsed.ok) return parsed.response;
  return proxyRequest(request, backendPath, {
    method: 'PUT',
    body: parsed.data,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function PATCH(request: Request, { params }: RouteContext) {
  const { path } = await params;
  const segments = path || [];
  if (segments.length === 0) {
    return Response.json({ error: 'Not Found' }, { status: 404 });
  }
  const { searchParams } = new URL(request.url);
  const backendPath = buildPath(segments, searchParams.toString());
  const parsed = await parseJsonBody(request);
  if (!parsed.ok) return parsed.response;
  return proxyRequest(request, backendPath, {
    method: 'PATCH',
    body: parsed.data,
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function DELETE(request: Request, { params }: RouteContext) {
  const { path } = await params;
  const segments = path || [];
  if (segments.length === 0) {
    return Response.json({ error: 'Not Found' }, { status: 404 });
  }
  const { searchParams } = new URL(request.url);
  const backendPath = buildPath(segments, searchParams.toString());
  return proxyRequest(request, backendPath, { method: 'DELETE' });
}
