import nextTs from 'eslint-config-next/typescript';
import nextVitals from 'eslint-config-next/core-web-vitals';
import { defineConfig, globalIgnores } from 'eslint/config';

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // 禁用 react-hooks/set-state-in-effect 规则
  // 该规则在 React 19 中新增，禁止在 useEffect 中调用 setState，
  // 但数据加载模式（useEffect 中调用含 setState 的异步函数）是常见且合理的用法
  {
    rules: {
      'react-hooks/set-state-in-effect': 'off',
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    '.next/**',
    'out/**',
    'build/**',
    'next-env.d.ts',
    // Build artifacts:
    'server.js',
    'dist/**',
  ]),
]);

export default eslintConfig;
