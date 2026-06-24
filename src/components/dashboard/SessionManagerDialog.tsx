'use client';

/**
 * 会话管理对话框
 *
 * 从 DashboardClient 拆分而来，隔离会话列表状态，
 * 避免会话开关操作触发整个仪表盘重渲染。
 */

import { useState, useEffect, useCallback } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Users, User, RefreshCw, MessageCircle } from 'lucide-react';
import { api, type SessionSummary } from '@/lib/api';

export function SessionManagerDialog() {
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<'all' | 'private' | 'group'>('all');

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getSessionSummaries();
      setSessions(data.sessions);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const handleToggleBot = async (sessionId: string, enabled: boolean) => {
    try {
      await api.toggleSessionBot(sessionId, enabled);
      setSessions(prev => prev.map(s =>
        s.sessionId === sessionId ? { ...s, botEnabled: enabled } : s
      ));
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    if (open) {
      loadSessions();
    }
  }, [open, loadSessions]);

  const filteredSessions = sessions.filter(s => filter === 'all' || s.sessionType === filter);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" className="flex flex-col items-center justify-center rounded-lg border p-4 h-auto hover:bg-muted transition-colors">
          <Users className="h-6 w-6 mb-2 text-primary" />
          <span className="text-sm font-medium">管理会话</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[650px] max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>会话管理</DialogTitle>
          <DialogDescription>
            查看各会话的对话概况，控制机器人在各会话中的启用状态
          </DialogDescription>
        </DialogHeader>
        {/* 筛选栏 */}
        <div className="flex items-center gap-2">
          <Select value={filter} onValueChange={(v) => setFilter(v as 'all' | 'private' | 'group')}>
            <SelectTrigger className="w-[120px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部会话</SelectItem>
              <SelectItem value="private">私聊</SelectItem>
              <SelectItem value="group">群聊</SelectItem>
            </SelectContent>
          </Select>
          <div className="flex-1" />
          <Button variant="secondary" size="sm" onClick={loadSessions} disabled={loading}>
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>
        <ScrollArea className="h-[420px]">
          {loading ? (
            <div className="space-y-3 p-2">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          ) : filteredSessions.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Users className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p>暂无会话记录</p>
            </div>
          ) : (
            <div className="space-y-2 p-1">
              {filteredSessions.map((session) => (
                <div key={session.sessionId} className="border rounded-lg p-3 hover:bg-accent/50 transition-colors">
                  {/* 头部：会话名 + 类型 + 开关 */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
                        session.sessionType === 'group' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
                      }`}>
                        {session.sessionType === 'group' ? <Users className="h-3.5 w-3.5" /> : <User className="h-3.5 w-3.5" />}
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{session.sessionName}</div>
                        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                          <Badge variant={session.sessionType === 'group' ? 'default' : 'secondary'} className="text-[10px] px-1.5 py-0">
                            {session.sessionType === 'group' ? '群聊' : '私聊'}
                          </Badge>
                          <span>{session.messageCount} 条消息</span>
                          <span>·</span>
                          <span>{new Date(session.lastActive).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Label htmlFor={`bot-${session.sessionId}`} className="text-xs text-muted-foreground cursor-pointer">
                        机器人
                      </Label>
                      <Switch
                        id={`bot-${session.sessionId}`}
                        checked={session.botEnabled}
                        onCheckedChange={(checked) => handleToggleBot(session.sessionId, checked)}
                      />
                    </div>
                  </div>
                  {/* 摘要 */}
                  {session.summary && (
                    <div className="flex gap-1.5 text-xs text-muted-foreground bg-muted/50 rounded px-2 py-1.5">
                      <MessageCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                      <p className="line-clamp-2">{session.summary}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
