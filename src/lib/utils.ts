/**
 * 工具函数模块
 *
 * 提供通用的工具函数，包括 className 合并等与 shadcn/ui 配合的辅助方法。
 *
 * @module utils
 */

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * 合并 Tailwind CSS 类名，自动处理冲突样式
 *
 * 结合 clsx（条件类名合并）和 tailwind-merge（智能去重），
 * 是 shadcn/ui 组件中 cn() 的标准实现。
 *
 * @param {...ClassValue[]} inputs - 类名参数，支持字符串、对象、数组等多种格式
 * @returns {string} 合并并去重后的 CSS 类名字符串
 *
 * @example
 * cn('px-4 py-2', isActive && 'bg-primary')
 * cn('text-red-500', 'text-blue-500') // => 'text-blue-500'（tailwind-merge 自动处理冲突）
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
