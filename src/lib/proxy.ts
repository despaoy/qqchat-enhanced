/**
 * API 代理工具函数
 * 统一处理后端代理请求，包括 Cookie→Authorization 转换、错误处理、超时控制
 */

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const PROXY_TIMEOUT = 30000; // 30秒超时

interface ProxyOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  timeout?: number;
}

/**
 * 代理请求到后端 FastAPI 服务
 *
 * 认证策略：
 * 1. 优先从 httpOnly Cookie (access_token) 中提取 JWT 转发给后端
 * 2. 回退到 Authorization header（向后兼容）
 */
export async function proxyRequest(
  request: Request,
  path: string,
  options: ProxyOptions = {}
): Promise<Response> {
  const { method = 'GET', body, headers: optHeaders = {}, timeout = PROXY_TIMEOUT } = options;
  const headers: Record<string, string> = { ...optHeaders };

  // 认证：优先从 Cookie 提取 token，回退到 Authorization header
  const cookieHeader = request.headers.get('Cookie') || '';
  const cookieToken = cookieHeader.split(';').find(c => c.trim().startsWith('access_token='));
  if (cookieToken) {
    const token = cookieToken.split('=')[1]?.trim();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }
  // 如果 Cookie 中没有 token，回退到 Authorization header
  if (!headers['Authorization']) {
    const authHeader = request.headers.get('Authorization');
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }
  }

  // 转发 Content-Type
  const contentType = request.headers.get('Content-Type');
  if (contentType && method !== 'GET') {
    headers['Content-Type'] = contentType;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const fetchOptions: RequestInit = {
      method,
      headers,
      signal: controller.signal,
    };

    if (body && method !== 'GET') {
      fetchOptions.body = typeof body === 'string' ? body : JSON.stringify(body);
    }

    const response = await fetch(`${BACKEND_URL}${path}`, fetchOptions);
    return response;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return new Response(JSON.stringify({ detail: '请求超时' }), {
        status: 504,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response(JSON.stringify({ detail: '后端服务不可用' }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    });
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * 代理 GET 请求
 */
export async function proxyGet(request: Request, path: string): Promise<Response> {
  return proxyRequest(request, path);
}

/**
 * 代理 POST 请求，自动读取请求体
 */
export async function proxyPost(request: Request, path: string): Promise<Response> {
  const body = await request.json();
  return proxyRequest(request, path, {
    method: 'POST',
    body,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * 代理 PUT 请求，自动读取请求体
 */
export async function proxyPut(request: Request, path: string): Promise<Response> {
  const body = await request.json();
  return proxyRequest(request, path, {
    method: 'PUT',
    body,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * 代理 PATCH 请求，自动读取请求体
 */
export async function proxyPatch(request: Request, path: string): Promise<Response> {
  const body = await request.json();
  return proxyRequest(request, path, {
    method: 'PATCH',
    body,
    headers: { 'Content-Type': 'application/json' },
  });
}

/**
 * 代理 DELETE 请求
 */
export async function proxyDelete(request: Request, path: string): Promise<Response> {
  return proxyRequest(request, path, { method: 'DELETE' });
}

export { BACKEND_URL };
