/**
 * 仪表盘首页
 *
 * 为应用入口页面，使用 AppLayout 布局包裹仪表盘客户端组件。
 * 定义页面 SEO 元数据（标题和描述），将实际的仪表盘交互逻辑委托给 DashboardClient 客户端组件。
 *
 * @module Dashboard
 * @see {@link ./DashboardClient.tsx} 仪表盘客户端组件
 */

import { AppLayout } from '@/components/layout/AppLayout';
import DashboardClient from './DashboardClient';

/** 页面 SEO 元数据 */
export const metadata = {
  title: '仪表盘 | QQ智能助手',
  description: 'QQ智能助手管理平台',
};

/**
 * 仪表盘页面组件（服务器组件）
 *
 * 负责：
 * - 导出页面 metadata（仅服务器组件可用）
 * - 组装 AppLayout 与 DashboardClient
 */
export default function Dashboard() {
  return (
    <AppLayout>
      <DashboardClient />
    </AppLayout>
  );
}
