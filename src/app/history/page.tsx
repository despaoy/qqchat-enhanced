'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Search, Download, Eye, Calendar, RefreshCw, AlertCircle, User, Bot, X, Trash2 } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import { useMessages } from '@/hooks/useMessages';
import { api, type LoraModel } from '@/lib/api';
import { format } from 'date-fns';
import type { Message } from '@/lib/api';

export default function HistoryPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [sessionType, setSessionType] = useState('all');
  const [sessionNameFilter, setSessionNameFilter] = useState('');
  const [selectedLora, setSelectedLora] = useState('all');
  const [detailMessage, setDetailMessage] = useState<Message | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [confirmBatchDelete, setConfirmBatchDelete] = useState(false);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [loraModels, setLoraModels] = useState<LoraModel[]>([]);
  const { messages, totalAll, loading, error, refetch } = useMessages(50, 0);

  // 加载 LoRA 模型列表
  const loadLoras = useCallback(async () => {
    try {
      const res = await api.getLoras();
      setLoraModels(res.loras);
    } catch {
      // 忽略，筛选框降级为无选项
    }
  }, []);

  useEffect(() => {
    loadLoras();
  }, [loadLoras]);

  // 从消息中提取实际出现的 loraName（去重）
  const loraNamesFromMessages = useMemo(() => {
    const names = new Set<string>();
    for (const msg of messages) {
      if (msg.loraName) names.add(msg.loraName);
    }
    return Array.from(names).sort();
  }, [messages]);

  // 过滤消息
  const filteredMessages = useMemo(() => {
    return messages.filter(msg => {
      const matchesSearch = !searchTerm || 
        msg.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
        msg.reply.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesType = sessionType === 'all' || msg.sessionType === sessionType;
      
      const matchesLora = selectedLora === 'all' ||
        msg.loraName === selectedLora;

      const matchesSessionName = !sessionNameFilter ||
        msg.sessionName.toLowerCase().includes(sessionNameFilter.toLowerCase());
      
      return matchesSearch && matchesType && matchesLora && matchesSessionName;
    });
  }, [messages, searchTerm, sessionType, selectedLora, sessionNameFilter]);

  // CSV 导出
  const handleExport = useCallback(() => {
    if (filteredMessages.length === 0) return;
    const headers = ['时间', '用户', '会话类型', '会话名称', '消息', '回复', '模型', 'LoRA', '耗时(s)'];
    const rows = filteredMessages.map(m => [
      format(new Date(m.createdAt), 'yyyy-MM-dd HH:mm:ss'),
      m.userName,
      m.sessionType === 'group' ? '群聊' : '私聊',
      m.sessionName,
      `"${m.message.replace(/"/g, '""')}"`,
      `"${m.reply.replace(/"/g, '""')}"`,
      m.modelName,
      m.loraName,
      m.costTime.toString(),
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `历史记录_${format(new Date(), 'yyyyMMdd_HHmmss')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [filteredMessages]);

  // 删除消息
  const handleDelete = useCallback(async (id: string) => {
    setDeletingId(id);
    try {
      await api.deleteMessage(id);
      await refetch();
    } catch (err) {
      console.error('Failed to delete message:', err);
    } finally {
      setDeletingId(null);
    }
  }, [refetch]);

  // 确认后执行删除
  const confirmDelete = useCallback((id: string) => {
    setConfirmDeleteId(id);
  }, []);

  const executeDelete = useCallback(() => {
    if (confirmDeleteId) {
      handleDelete(confirmDeleteId);
      setConfirmDeleteId(null);
    }
  }, [confirmDeleteId, handleDelete]);

  const cancelDelete = useCallback(() => {
    setConfirmDeleteId(null);
  }, []);

  // 批量删除全部（基于筛选条件）
  const handleBatchDelete = useCallback(async () => {
    setBatchDeleting(true);
    setConfirmBatchDelete(false);
    try {
      const filters: Record<string, string> = {};
      if (searchTerm) filters.search = searchTerm;
      if (sessionType && sessionType !== 'all') filters.sessionType = sessionType;
      if (selectedLora && selectedLora !== 'all') filters.lora = selectedLora;
      if (sessionNameFilter) filters.sessionName = sessionNameFilter;
      
      const result = await api.deleteMessagesBatch(filters);
      console.log(`已删除 ${result.deleted} 条记录`);
      await refetch();
    } catch (err) {
      console.error('Failed to batch delete messages:', err);
    } finally {
      setBatchDeleting(false);
    }
  }, [searchTerm, sessionType, selectedLora, sessionNameFilter, refetch]);

  if (error) {
    return (
      <AppLayout>
        <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <div className="text-center">
            <h3 className="text-lg font-semibold">加载失败</h3>
            <p className="text-muted-foreground">{error}</p>
          </div>
          <Button onClick={refetch}>
            <RefreshCw className="mr-2 h-4 w-4" />
            重试
          </Button>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">历史记录</h2>
            <p className="text-muted-foreground">查看和管理所有对话历史记录</p>
          </div>
          <Button variant="ghost" size="icon" onClick={refetch} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>筛选条件</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-4 md:flex-row">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="搜索消息内容..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-8"
                  />
                </div>
              </div>
              <Select value={sessionType} onValueChange={setSessionType}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="会话类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
                  <SelectItem value="group">群聊</SelectItem>
                  <SelectItem value="private">私聊</SelectItem>
                </SelectContent>
              </Select>
              <Select value={selectedLora} onValueChange={setSelectedLora}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="LoRA模型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
                  {loraNamesFromMessages.map((name) => (
                    <SelectItem key={name} value={name}>
                      {name === 'default' ? '基础模型（无LoRA）' : name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                placeholder="群聊名/私聊名称..."
                value={sessionNameFilter}
                onChange={(e) => setSessionNameFilter(e.target.value)}
                className="w-[200px]"
              />
              <Button onClick={handleExport}>
                <Download className="mr-2 h-4 w-4" />
                导出数据
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>对话记录</CardTitle>
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">
                 共 {totalAll} 条记录{filteredMessages.length !== totalAll ? `（当前筛选 ${filteredMessages.length} 条）` : ''}
               </span>
              <Button
                variant="destructive"
                size="sm"
                disabled={batchDeleting || filteredMessages.length === 0}
                onClick={() => setConfirmBatchDelete(true)}
              >
                {batchDeleting ? '删除中...' : '删除全部'}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="flex items-center gap-4">
                    <Skeleton className="h-8 w-8 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-4 w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>时间</TableHead>
                    <TableHead>用户</TableHead>
                    <TableHead>会话</TableHead>
                    <TableHead>消息预览</TableHead>
                    <TableHead>LoRA模型</TableHead>
                    <TableHead>耗时</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredMessages.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        <div className="text-muted-foreground">暂无记录</div>
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredMessages.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="text-sm text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {format(new Date(item.createdAt), 'yyyy-MM-dd HH:mm:ss')}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Avatar className="h-8 w-8">
                              <AvatarImage src="" />
                              <AvatarFallback>{item.userName[0]}</AvatarFallback>
                            </Avatar>
                            <span className="font-medium">{item.userName}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={item.sessionType === 'group' ? 'default' : 'secondary'}>
                            {item.sessionType === 'group' ? '群聊' : '私聊'}
                          </Badge>
                          <div className="text-sm text-muted-foreground mt-1">{item.sessionName}</div>
                        </TableCell>
                        <TableCell className="max-w-[200px]">
                          <p className="truncate text-sm">{item.message}</p>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">{item.loraName === 'default' ? '基础模型（无LoRA）' : (item.loraName || item.modelName || '-')}</div>
                          {item.loraName && item.loraName !== 'default' && item.modelName && (
                            <div className="text-xs text-muted-foreground">{item.modelName}</div>
                          )}
                        </TableCell>
                        <TableCell className="text-sm">{item.costTime}s</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Button variant="ghost" size="icon" onClick={() => setDetailMessage(item)}>
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => confirmDelete(String(item.id))}
                              disabled={deletingId === String(item.id)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* 批量删除确认弹窗 */}
        <Dialog open={confirmBatchDelete} onOpenChange={setConfirmBatchDelete}>
          <DialogContent className="sm:max-w-[450px]">
            <DialogHeader>
              <DialogTitle>确认批量删除</DialogTitle>
            </DialogHeader>
            <div className="space-y-2">
              <p className="text-muted-foreground">
                将删除当前筛选条件下的 <strong>{filteredMessages.length}</strong> 条对话记录，此操作不可撤销。
              </p>
              {(searchTerm || sessionType !== 'all' || selectedLora !== 'all' || sessionNameFilter) && (
                <div className="text-xs text-muted-foreground bg-muted rounded-md p-2 space-y-0.5">
                  <p>当前筛选条件：</p>
                  {searchTerm && <p>· 搜索：{searchTerm}</p>}
                  {sessionType !== 'all' && <p>· 类型：{sessionType === 'group' ? '群聊' : '私聊'}</p>}
                  {selectedLora !== 'all' && <p>· LoRA：{selectedLora}</p>}
                  {sessionNameFilter && <p>· 会话名：{sessionNameFilter}</p>}
                </div>
              )}
            </div>
            <div className="flex justify-end gap-3 mt-4">
              <Button variant="outline" onClick={() => setConfirmBatchDelete(false)}>取消</Button>
              <Button variant="destructive" onClick={handleBatchDelete}>确认删除</Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* 删除确认弹窗 */}
        <Dialog open={!!confirmDeleteId} onOpenChange={(open) => { if (!open) cancelDelete(); }}>
          <DialogContent className="sm:max-w-[400px]">
            <DialogHeader>
              <DialogTitle>确认删除</DialogTitle>
            </DialogHeader>
            <p className="text-muted-foreground">确定要删除这条记录吗？此操作不可撤销。</p>
            <div className="flex justify-end gap-3 mt-4">
              <Button variant="outline" onClick={cancelDelete}>取消</Button>
              <Button variant="destructive" onClick={executeDelete}>删除</Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* 对话详情弹窗 */}
        <Dialog open={!!detailMessage} onOpenChange={(open) => { if (!open) setDetailMessage(null); }}>
          <DialogContent className="sm:max-w-[600px] max-h-[85vh] flex flex-col">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5" />
                对话详情
              </DialogTitle>
            </DialogHeader>
            {detailMessage && (
              <div className="space-y-4 overflow-y-auto flex-1 min-h-0">
                {/* 元信息 */}
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <Badge variant={detailMessage.sessionType === 'group' ? 'default' : 'secondary'}>
                    {detailMessage.sessionType === 'group' ? '群聊' : '私聊'}
                  </Badge>
                  <span>{detailMessage.sessionName}</span>
                  <span>·</span>
                  <span>{format(new Date(detailMessage.createdAt), 'yyyy-MM-dd HH:mm:ss')}</span>
                  <span>·</span>
                  <span>{detailMessage.modelName}</span>
                  {detailMessage.loraName && detailMessage.loraName !== 'default' && (
                    <>
                      <span>·</span>
                      <span>LoRA: {detailMessage.loraName}</span>
                    </>
                  )}
                  <span>·</span>
                  <span>耗时 {detailMessage.costTime}s</span>
                </div>

                <Separator />

                {/* 用户消息 */}
                <div className="flex gap-3">
                  <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-blue-100 text-blue-700">
                    <User className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-muted-foreground mb-1">
                      {detailMessage.userName}
                    </div>
                    <div className="bg-blue-50 dark:bg-blue-950/20 rounded-lg p-3 text-sm whitespace-pre-wrap break-words">
                      {detailMessage.message}
                    </div>
                  </div>
                </div>

                {/* 机器人回复 */}
                <div className="flex gap-3">
                  <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-purple-100 text-purple-700">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-muted-foreground mb-1">
                      {detailMessage.modelName}
                    </div>
                    <div className="bg-purple-50 dark:bg-purple-950/20 rounded-lg p-3 text-sm whitespace-pre-wrap break-words">
                      {detailMessage.reply}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}
