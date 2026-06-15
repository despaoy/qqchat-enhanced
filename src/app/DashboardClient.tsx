'use client';

/**
 * 仪表盘客户端组件
 *
 * 智能助手管理平台的首页仪表盘，展示：
 * - 四个统计卡片（今日回复数、平均响应时间、活跃会话、模型负载）
 * - 24 小时活动趋势折线图
 * - 系统状态面板（模型信息、系统资源、服务状态）
 * - 快捷操作入口（测试回复、切换模型、重启服务、管理会话）
 */

import { useState, useEffect, useRef } from 'react';
import { StatCard } from '@/components/dashboard/StatCard';
import { ActivityChart } from '@/components/dashboard/ActivityChart';
import { MessageSquare, Zap, Clock, Users, BrainCircuit, RefreshCw, AlertCircle, Send, Bot, User, Trash2, MessageCircle, LogIn } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Switch } from '@/components/ui/switch';
import { useStats } from '@/hooks/useStats';
import { useLoras } from '@/hooks/useLoras';
import { useServices } from '@/hooks/useServices';
import { api, type SessionSummary } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  loraName?: string;
  costTime?: number;
}

export default function DashboardClient() {
  const { user, loading: authLoading } = useAuth();
  const { stats, loading: statsLoading, error: statsError, refetch: refetchStats } = useStats(!!user && !authLoading);
  const { loras } = useLoras(!!user && !authLoading);
  const { services, loading: servicesLoading, error: servicesError, refetch: refetchServices } = useServices(!!user && !authLoading);

  // 测试对话状态
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [selectedLora, setSelectedLora] = useState('');
  const [sessionType, setSessionType] = useState<'private' | 'group'>('private');
  const [chatDialogOpen, setChatDialogOpen] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // 管理会话状态
  const [sessionDialogOpen, setSessionDialogOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessionFilter, setSessionFilter] = useState<'all' | 'private' | 'group'>('all');

  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // 聊天消息自动滚动到底部
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // 获取当前激活的LoRA
  const activeLora = loras.find(lora => lora.status === 'active');

  // 发送聊天消息
  const handleSendMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;

    const userMsg: ChatMessage = { role: 'user', content: chatInput };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setChatLoading(true);

    try {
      const response = await api.generateReply({
        message: chatInput,
        sessionType,
        sessionId: sessionType === 'group' ? 'test-group' : 'test-private',
        userId: 'dashboard-user',
        userName: sessionType === 'group' ? '群成员' : '测试用户',
        loraName: selectedLora || undefined,
      });
      const botMsg: ChatMessage = {
        role: 'assistant',
        content: response.reply,
        loraName: selectedLora || 'default',
        costTime: response.costTime,
      };
      setChatMessages(prev => [...prev, botMsg]);
    } catch (err) {
      console.error('Failed to generate reply:', err);
      setChatMessages(prev => [...prev, { role: 'assistant', content: '生成失败，请稍后重试' }]);
    } finally {
      setChatLoading(false);
    }
  };

  // 加载会话列表
  const loadSessions = async () => {
    setSessionLoading(true);
    try {
      const data = await api.getSessionSummaries();
      setSessions(data.sessions);
    } catch {
      // ignore
    } finally {
      setSessionLoading(false);
    }
  };

  // 切换会话机器人开关
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

  // 打开会话管理对话框时加载数据
  useEffect(() => {
    if (sessionDialogOpen) {
      loadSessions();
    }
  }, [sessionDialogOpen]);

  if (statsError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <div className="text-center">
          <h3 className="text-lg font-semibold">加载失败</h3>
          <p className="text-muted-foreground">{statsError}</p>
        </div>
        <Button onClick={refetchStats}>
          <RefreshCw className="mr-2 h-4 w-4" />
          重试
        </Button>
      </div>
    );
  }

  if (authLoading || !isMounted) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">仪表盘</h2>
            <p className="text-muted-foreground">
              欢迎回来！查看您的智能助手运行状态和最新活动。
            </p>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <LogIn className="h-12 w-12 text-muted-foreground" />
        <div className="text-center">
          <h3 className="text-lg font-semibold">请先登录</h3>
          <p className="text-muted-foreground">登录后即可查看仪表盘</p>
        </div>
        <Button onClick={() => window.location.href = '/login'}>
          <LogIn className="mr-2 h-4 w-4" />
          前往登录
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">仪表盘</h2>
          <p className="text-muted-foreground">
            欢迎回来！查看您的智能助手运行状态和最新活动。
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={() => { refetchStats(); refetchServices(); }} disabled={statsLoading || servicesLoading}>
          <RefreshCw className={`h-4 w-4 ${(statsLoading || servicesLoading) ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statsLoading ? (
          <>
            <Skeleton className="h-32 rounded-lg" />
            <Skeleton className="h-32 rounded-lg" />
            <Skeleton className="h-32 rounded-lg" />
            <Skeleton className="h-32 rounded-lg" />
          </>
        ) : (
          <>
            <StatCard
              title="今日回复数"
              value={stats?.todayReplies?.toString() || '0'}
              icon={MessageSquare}
            />
            <StatCard
              title="平均响应时间"
              value={`${stats?.avgResponseTime || 0}s`}
              icon={Clock}
            />
            <StatCard
              title="活跃会话"
              value={stats?.activeSessions?.toString() || '0'}
              icon={Users}
            />
            <StatCard
              title="模型负载"
              value={`${stats?.modelLoad || 0}%`}
              icon={Zap}
            />
          </>
        )}
      </div>

      {/* 图表和模型状态 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ActivityChart />
        </div>
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BrainCircuit className="h-5 w-5" />
                系统状态
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {(statsLoading || servicesLoading) ? (
                <>
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-3/4" />
                </>
              ) : (
                <>
                  {/* 模型信息 */}
                  <div className="pb-3 border-b">
                    <h4 className="text-sm font-semibold mb-2 text-muted-foreground">模型信息</h4>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm">基座模型</span>
                      <span className="text-sm font-medium">Qwen2.5-7B</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">当前LoRA</span>
                      <span className="text-sm font-medium text-primary">
                        {activeLora?.name || '基础模型（无LoRA）'}
                      </span>
                    </div>
                  </div>

                  {/* 系统资源 */}
                  <div className="pb-3 border-b">
                    <h4 className="text-sm font-semibold mb-2 text-muted-foreground">系统资源</h4>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm">CPU使用率</span>
                      <span className="text-sm font-medium">{stats?.cpuUsage || 0}%</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm">内存使用</span>
                      <span className="text-sm font-medium">
                        {stats?.memoryUsage?.used || 0}GB / {stats?.memoryUsage?.total || 16}GB
                      </span>
                    </div>
                  </div>

                  {/* 服务状态 */}
                  <div>
                    <h4 className="text-sm font-semibold mb-2 text-muted-foreground">服务状态</h4>
                    {servicesError ? (
                      <div className="text-sm text-destructive">{servicesError}</div>
                    ) : (
                      <div className="space-y-2">
                        {services.map((service, index) => (
                          <div key={index} className="flex items-center justify-between">
                            <span className="text-sm">{service.name}</span>
                            <div className="flex items-center gap-2">
                              <div className={`w-2 h-2 rounded-full ${
                                service.status === 'running' ? 'bg-green-500' :
                                service.status === 'connecting' ? 'bg-yellow-500' : 'bg-red-500'
                              }`} />
                              <span className={`text-xs font-medium ${
                                service.status === 'running' ? 'text-green-600' :
                                service.status === 'connecting' ? 'text-yellow-600' : 'text-red-600'
                              }`}>
                                {service.status === 'running' ? '运行中' :
                                 service.status === 'connecting' ? '连接中' : '已停止'}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 快捷操作 */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>快捷操作</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid grid-cols-2 gap-3">
              {/* 测试回复 - 聊天式对话 */}
              <Dialog open={chatDialogOpen} onOpenChange={setChatDialogOpen}>
                <DialogTrigger asChild>
                  <Button variant="ghost" className="flex flex-col items-center justify-center rounded-lg border p-4 h-auto hover:bg-muted transition-colors">
                    <MessageSquare className="h-6 w-6 mb-2 text-primary" />
                    <span className="text-sm font-medium">测试回复</span>
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-[550px] max-h-[85vh] flex flex-col">
                  <DialogHeader>
                    <DialogTitle>测试机器人回复</DialogTitle>
                    <DialogDescription>
                      模拟私聊或群聊场景，测试不同LoRA的回复效果
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-3 overflow-y-auto flex-1 min-h-0">
                    {/* 配置栏 */}
                    <div className="flex gap-2">
                      <Select value={sessionType} onValueChange={(v) => setSessionType(v as 'private' | 'group')}>
                        <SelectTrigger className="w-[100px] h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="private">私聊</SelectItem>
                          <SelectItem value="group">群聊</SelectItem>
                        </SelectContent>
                      </Select>
                      <Select value={selectedLora} onValueChange={setSelectedLora}>
                        <SelectTrigger className="flex-1 h-8 text-xs">
                          <SelectValue placeholder="选择LoRA模型" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="default">基础模型（无LoRA）</SelectItem>
                          {loras.map((lora) => (
                            <SelectItem key={lora.id} value={lora.name}>
                              {lora.name} {lora.status === 'active' ? '(激活)' : ''}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 shrink-0"
                        onClick={() => setChatMessages([])}
                        title="清空对话"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>

                    <Separator />

                    {/* 聊天区域 */}
                    <ScrollArea className="h-[300px] rounded-lg border p-3">
                      {chatMessages.length === 0 ? (
                        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                          发送一条消息开始测试
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {chatMessages.map((msg, i) => (
                            <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                              {msg.role === 'assistant' && (
                                <div className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center bg-purple-100 text-purple-700">
                                  <Bot className="h-3.5 w-3.5" />
                                </div>
                              )}
                              <div className={`max-w-[75%] rounded-lg p-2.5 text-sm ${
                                msg.role === 'user'
                                  ? 'bg-primary text-primary-foreground'
                                  : 'bg-muted'
                              }`}>
                                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                                {msg.role === 'assistant' && msg.costTime && (
                                  <p className="text-[10px] text-muted-foreground mt-1">
                                    {msg.loraName || 'default'} · {msg.costTime}s
                                  </p>
                                )}
                              </div>
                              {msg.role === 'user' && (
                                <div className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center bg-blue-100 text-blue-700">
                                  <User className="h-3.5 w-3.5" />
                                </div>
                              )}
                            </div>
                          ))}
                          {chatLoading && (
                            <div className="flex gap-2 justify-start">
                              <div className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center bg-purple-100 text-purple-700">
                                <Bot className="h-3.5 w-3.5" />
                              </div>
                              <div className="bg-muted rounded-lg p-2.5 text-sm text-muted-foreground">
                                正在思考...
                              </div>
                            </div>
                          )}
                          <div ref={chatEndRef} />
                        </div>
                      )}
                    </ScrollArea>

                    {/* 输入区域 */}
                    <div className="flex gap-2">
                      <Input
                        placeholder={sessionType === 'group' ? '在群聊中发送消息...' : '发送消息...'}
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            handleSendMessage();
                          }
                        }}
                        disabled={chatLoading}
                      />
                      <Button size="icon" onClick={handleSendMessage} disabled={chatLoading || !chatInput.trim()}>
                        <Send className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>

              {/* 切换模型 */}
              <Dialog>
                <DialogTrigger asChild>
                  <Button variant="ghost" className="flex flex-col items-center justify-center rounded-lg border p-4 h-auto hover:bg-muted transition-colors">
                    <BrainCircuit className="h-6 w-6 mb-2 text-primary" />
                    <span className="text-sm font-medium">切换模型</span>
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-[450px] max-h-[85vh] flex flex-col">
                  <DialogHeader>
                    <DialogTitle>切换LoRA模型</DialogTitle>
                    <DialogDescription>
                      选择要激活的LoRA模型，切换后所有新消息将使用该模型回复
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-2 py-4 overflow-y-auto flex-1 min-h-0">
                    {loras.length === 0 ? (
                      <div className="text-center py-8 text-muted-foreground">
                        暂无LoRA模型，请先在LoRA管理页面添加
                      </div>
                    ) : (
                      loras.map((lora) => (
                        <div key={lora.id} className="flex items-center justify-between p-3 rounded-lg border">
                          <div>
                            <div className="font-medium text-sm">{lora.name}</div>
                            <div className="text-xs text-muted-foreground">{lora.description || lora.style}</div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={lora.status === 'active' ? 'default' : 'secondary'} className="text-xs">
                              {lora.status === 'active' ? '激活中' : '未激活'}
                            </Badge>
                            {lora.status !== 'active' && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={async () => {
                                  try {
                                    await api.toggleLoraStatus(lora.id, lora.status);
                                  } catch {
                                    // ignore
                                  }
                                }}
                              >
                                激活
                              </Button>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </DialogContent>
              </Dialog>

              {/* 重启服务 */}
              <Button variant="ghost" className="flex flex-col items-center justify-center rounded-lg border p-4 h-auto hover:bg-muted transition-colors">
                <Zap className="h-6 w-6 mb-2 text-primary" />
                <span className="text-sm font-medium">重启服务</span>
              </Button>

              {/* 管理会话 */}
              <Dialog open={sessionDialogOpen} onOpenChange={setSessionDialogOpen}>
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
                    <Select value={sessionFilter} onValueChange={(v) => setSessionFilter(v as 'all' | 'private' | 'group')}>
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
                    <Button variant="secondary" size="sm" onClick={loadSessions} disabled={sessionLoading}>
                      <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${sessionLoading ? 'animate-spin' : ''}`} />
                      刷新
                    </Button>
                  </div>
                  <ScrollArea className="h-[420px]">
                    {sessionLoading ? (
                      <div className="space-y-3 p-2">
                        {[1, 2, 3, 4].map((i) => (
                          <Skeleton key={i} className="h-24 w-full" />
                        ))}
                      </div>
                    ) : sessions.filter(s => sessionFilter === 'all' || s.sessionType === sessionFilter).length === 0 ? (
                      <div className="text-center py-12 text-muted-foreground">
                        <Users className="h-10 w-10 mx-auto mb-3 opacity-30" />
                        <p>暂无会话记录</p>
                      </div>
                    ) : (
                      <div className="space-y-2 p-1">
                        {sessions
                          .filter(s => sessionFilter === 'all' || s.sessionType === sessionFilter)
                          .map((session) => (
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
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
