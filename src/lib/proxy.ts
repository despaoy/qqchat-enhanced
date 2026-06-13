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
 * 1. 从 httpOnly Cookie (access_token) 中提取 JWT，转为 Authorization: Bearer 头转发
 *    （Node.js fetch 会忽略手动设置的 Cookie 头，因此必须转为 Authorization 头）
 * 2. 回退到原始 Authorization header（向后兼容）
 */
export async function proxyRequest(
  request: Request,
  path: string,
  options: ProxyOptions = {}
): Promise<Response> {
  const { method = 'GET', body, headers: optHeaders = {}, timeout = PROXY_TIMEOUT } = options;
  const headers: Record<string, string> = { ...optHeaders };

  // 认证：从 Cookie 中提取 JWT token，转为 Authorization 头转发
  // 注意：Node.js fetch 会忽略手动设置的 Cookie 头，必须用 Authorization 头传递认证信息
  const cookieHeader = request.headers.get('Cookie') || '';
  if (cookieHeader) {
    // 正确解析 Cookie：用 substring 而非 split('=') 避免 JWT 中的 = 字符被截断
    const cookieParts = cookieHeader.split(';');
    for (const part of cookieParts) {
      const trimmed = part.trim();
      if (trimmed.startsWith('access_token=')) {
        const token = trimmed.substring('access_token='.length);
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        break;
      }
    }
  }
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
