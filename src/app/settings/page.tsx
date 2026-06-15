'use client';

import { useState, useEffect, useCallback } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { AuthGuard } from '@/components/layout/AuthGuard';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Settings, Bot, Database, Bell, Shield, Save, RefreshCw, AlertCircle, CheckCircle2, Cpu, MemoryStick, ArrowRightLeft, Zap, BookOpen } from 'lucide-react';
import { api, SystemConfig, AvailableModel, ModuleStatusResponse } from '@/lib/api';
import { toast } from 'sonner';
import { useSettings } from '@/contexts/SettingsContext';
import { getSupportedLocales, getSupportedTimezones } from '@/lib/i18n';

export default function SettingsPage() {
  return (
    <AuthGuard>
      <SettingsContent />
    </AuthGuard>
  );
}

function SettingsContent() {
  const { t, updateSettings } = useSettings();
  const [config, setConfig] = useState<SystemConfig>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<AvailableModel[]>([]);
  const [moduleStatus, setModuleStatus] = useState<ModuleStatusResponse | null>(null);
  const [switching, setSwitching] = useState(false);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [configData, modelsData] = await Promise.all([
        api.getConfig(),
        api.getModels(),
      ]);
      setConfig(configData.config);
      setAvailableModels(modelsData.models);
      // 获取模块状态
      try { setModuleStatus(await api.getModuleStatus()); } catch {}
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.loadFailed'));
      console.error('Failed to fetch config:', err);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchConfig();
  }, [fetchConfig]);

  const updateField = (key: string, value: string | number | boolean) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const result = await api.updateConfig(config);
      if (result.success) {
        setConfig(result.config);
        // 如果模型提供商变更，同步切换后端提供商
        if (config.modelProvider) {
          try {
            await fetch('/api/model/provider', {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ provider: config.modelProvider }),
            });
          } catch {
            // 提供商切换失败不阻塞保存
          }
        }
        // 立即刷新全局设置，使语言/时区变更即时生效
        await updateSettings(result.config);
        toast.success(t('settings.saved'));
      }
    } catch (err) {
      toast.error(t('settings.saveFailed'));
      console.error('Failed to save config:', err);
    } finally {
      setSaving(false);
    }
  };

  const getBool = (key: string, fallback = true): boolean => {
    const val = config[key];
    if (typeof val === 'boolean') return val;
    if (typeof val === 'string') return val.toLowerCase() === 'true';
    return fallback;
  };

  const getStr = (key: string, fallback = ''): string => {
    const val = config[key];
    return val != null ? String(val) : fallback;
  };

  const getNum = (key: string, fallback = 0): number => {
    const val = config[key];
    if (typeof val === 'number') return val;
    if (typeof val === 'string') {
      const n = Number(val);
      return isNaN(n) ? fallback : n;
    }
    return fallback;
  };

  if (error && !Object.keys(config).length) {
    return (
      <AppLayout>
        <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <div className="text-center">
            <h3 className="text-lg font-semibold">{t('settings.loadError')}</h3>
            <p className="text-muted-foreground">{error}</p>
          </div>
          <Button onClick={fetchConfig}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {t('settings.retry')}
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
            <h2 className="text-2xl font-bold tracking-tight">{t('settings.title')}</h2>
            <p className="text-muted-foreground">{t('settings.description')}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={fetchConfig} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        <Tabs defaultValue="general" className="space-y-4">
          <TabsList>
            <TabsTrigger value="general" className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              {t('settings.tab.general')}
            </TabsTrigger>
            <TabsTrigger value="bot" className="flex items-center gap-2">
              <Bot className="h-4 w-4" />
              {t('settings.tab.bot')}
            </TabsTrigger>
            <TabsTrigger value="model" className="flex items-center gap-2">
              <Database className="h-4 w-4" />
              {t('settings.tab.model')}
            </TabsTrigger>
            <TabsTrigger value="notifications" className="flex items-center gap-2">
              <Bell className="h-4 w-4" />
              {t('settings.tab.notifications')}
            </TabsTrigger>
            <TabsTrigger value="security" className="flex items-center gap-2">
              <Shield className="h-4 w-4" />
              {t('settings.tab.security')}
            </TabsTrigger>
            <TabsTrigger value="module" className="flex items-center gap-2">
              <ArrowRightLeft className="h-4 w-4" />
              模块模式
            </TabsTrigger>
          </TabsList>

          <TabsContent value="general" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.general.title')}</CardTitle>
                <CardDescription>{t('settings.general.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {loading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="space-y-2">
                      <Skeleton className="h-4 w-16" />
                      <Skeleton className="h-10 w-full" />
                    </div>
                  ))
                ) : (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="system-name">{t('settings.general.systemName')}</Label>
                      <Input
                        id="system-name"
                        value={getStr('botName', 'QQ智能助手')}
                        onChange={(e) => updateField('botName', e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="language">{t('settings.general.language')}</Label>
                      <Select
                        value={getStr('language', 'zh-CN')}
                        onValueChange={(v) => updateField('language', v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t('settings.general.language')} />
                        </SelectTrigger>
                        <SelectContent>
                          {getSupportedLocales().map((loc) => (
                            <SelectItem key={loc.value} value={loc.value}>
                              {t(`settings.general.language.${loc.value === 'zh-CN' ? 'zhCN' : loc.value === 'zh-TW' ? 'zhTW' : 'en'}`)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="timezone">{t('settings.general.timezone')}</Label>
                      <Select
                        value={getStr('timezone', 'Asia/Shanghai')}
                        onValueChange={(v) => updateField('timezone', v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t('settings.general.timezone')} />
                        </SelectTrigger>
                        <SelectContent>
                          {getSupportedTimezones().map((tz) => (
                            <SelectItem key={tz.value} value={tz.value}>
                              {t(tz.labelKey)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="bot" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.bot.title')}</CardTitle>
                <CardDescription>{t('settings.bot.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <Skeleton className="h-4 w-32" />
                      <Skeleton className="h-6 w-10" />
                    </div>
                  ))
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>{t('settings.bot.autoReply')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.bot.autoReplyDesc')}</p>
                      </div>
                      <Switch
                        checked={getBool('autoReply', true)}
                        onCheckedChange={(v) => updateField('autoReply', v)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>{t('settings.bot.groupReply')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.bot.groupReplyDesc')}</p>
                      </div>
                      <Switch
                        checked={getBool('groupReply', true)}
                        onCheckedChange={(v) => updateField('groupReply', v)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>{t('settings.bot.privateReply')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.bot.privateReplyDesc')}</p>
                      </div>
                      <Switch
                        checked={getBool('privateReply', true)}
                        onCheckedChange={(v) => updateField('privateReply', v)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('settings.bot.replyDelay')}</Label>
                      <Input
                        type="number"
                        value={getNum('replyDelay', 1)}
                        min={0}
                        max={10}
                        onChange={(e) => updateField('replyDelay', Number(e.target.value))}
                      />
                      <p className="text-sm text-muted-foreground">{t('settings.bot.replyDelayDesc')}</p>
                    </div>
                    <div className="space-y-2">
                      <Label>{t('settings.bot.defaultTemplate')}</Label>
                      <Textarea
                        placeholder={t('settings.bot.defaultTemplatePlaceholder')}
                        value={getStr('defaultReplyTemplate', '')}
                        onChange={(e) => updateField('defaultReplyTemplate', e.target.value)}
                      />
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="model" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.model.title')}</CardTitle>
                <CardDescription>{t('settings.model.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="space-y-2">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-10 w-full" />
                    </div>
                  ))
                ) : (
                  <>
                    <div className="space-y-2">
                      <Label>{t('settings.model.provider')}</Label>
                      <p className="text-sm text-muted-foreground">{t('settings.model.providerDesc')}</p>
                      <Select
                        value={getStr('modelProvider', 'mock')}
                        onValueChange={(v) => updateField('modelProvider', v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t('settings.model.provider')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="openai_compat">DeepSeek / OpenAI 兼容 API</SelectItem>
                          <SelectItem value="ollama">Ollama (本地)</SelectItem>
                          <SelectItem value="llama_cpp">llama.cpp (本地)</SelectItem>
                          <SelectItem value="mock">Mock (测试)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    {getStr('modelProvider', 'mock') === 'openai_compat' && (
                      <div className="space-y-4 rounded-lg border p-4 bg-muted/30">
                        <div className="space-y-2">
                          <Label>{t('settings.model.apiBaseUrl')}</Label>
                          <p className="text-sm text-muted-foreground">{t('settings.model.apiBaseUrlDesc')}</p>
                          <Input
                            value={getStr('openaiCompatBaseUrl', 'https://api.deepseek.com')}
                            onChange={(e) => updateField('openaiCompatBaseUrl', e.target.value)}
                            placeholder="https://api.deepseek.com"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t('settings.model.apiKey')}</Label>
                          <p className="text-sm text-muted-foreground">{t('settings.model.apiKeyDesc')}</p>
                          <Input
                            type="password"
                            value={getStr('openaiCompatApiKey', '')}
                            onChange={(e) => updateField('openaiCompatApiKey', e.target.value)}
                            placeholder="sk-..."
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t('settings.model.apiModel')}</Label>
                          <p className="text-sm text-muted-foreground">{t('settings.model.apiModelDesc')}</p>
                          <Input
                            value={getStr('openaiCompatModel', 'deepseek-chat')}
                            onChange={(e) => updateField('openaiCompatModel', e.target.value)}
                            placeholder="deepseek-chat"
                          />
                        </div>
                      </div>
                    )}
                    <div className="space-y-2">
                      <Label>{t('settings.model.baseModel')}</Label>
                      <Select
                        value={getStr('baseModel', 'qwen2.5-7b')}
                        onValueChange={(v) => updateField('baseModel', v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t('settings.model.baseModel')} />
                        </SelectTrigger>
                        <SelectContent>
                          {availableModels.map((model) => (
                            <SelectItem key={model.name} value={model.name}>
                              {model.display_name} {!model.downloaded ? '(未下载)' : ''}
                            </SelectItem>
                          ))}
                          {availableModels.length === 0 && (
                            <SelectItem value="qwen2.5-7b">Qwen2.5-7B</SelectItem>
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>{t('settings.model.temperature')}</Label>
                      <Input
                        type="number"
                        value={getNum('temperature', 0.7)}
                        min={0}
                        max={2}
                        step={0.1}
                        onChange={(e) => updateField('temperature', Number(e.target.value))}
                      />
                      <p className="text-sm text-muted-foreground">{t('settings.model.temperatureDesc')}</p>
                    </div>
                    <div className="space-y-2">
                      <Label>{t('settings.model.maxLength')}</Label>
                      <Input
                        type="number"
                        value={getNum('maxTokens', 2048)}
                        min={256}
                        max={8192}
                        step={256}
                        onChange={(e) => updateField('maxTokens', Number(e.target.value))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('settings.model.contextWindow')}</Label>
                      <Select
                        value={getStr('contextWindow', '8k')}
                        onValueChange={(v) => updateField('contextWindow', v)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder={t('settings.model.contextWindow')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="4k">4K tokens</SelectItem>
                          <SelectItem value="8k">8K tokens</SelectItem>
                          <SelectItem value="16k">16K tokens</SelectItem>
                          <SelectItem value="32k">32K tokens</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>{t('settings.model.useKnowledge')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.model.useKnowledgeDesc')}</p>
                      </div>
                      <Switch
                        checked={getBool('useKnowledgeBase', true)}
                        onCheckedChange={(v) => updateField('useKnowledgeBase', v)}
                      />
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="notifications" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.notifications.title')}</CardTitle>
                <CardDescription>{t('settings.notifications.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {loading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-6 w-10" />
                    </div>
                  ))
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>{t('settings.notifications.errorAlert')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.notifications.errorAlertDesc')}</p>
                      </div>
                      <Switch
                        checked={getBool('errorAlert', true)}
                        onCheckedChange={(v) => updateField('errorAlert', v)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>{t('settings.notifications.dailyStats')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.notifications.dailyStatsDesc')}</p>
                      </div>
                      <Switch
                        checked={getBool('dailyStats', true)}
                        onCheckedChange={(v) => updateField('dailyStats', v)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>{t('settings.notifications.anomalyDetection')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.notifications.anomalyDetectionDesc')}</p>
                      </div>
                      <Switch
                        checked={getBool('anomalyDetection', false)}
                        onCheckedChange={(v) => updateField('anomalyDetection', v)}
                      />
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="security" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('settings.security.title')}</CardTitle>
                <CardDescription>{t('settings.security.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {loading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="space-y-2">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-10 w-full" />
                    </div>
                  ))
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>{t('settings.security.contentFilter')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.security.contentFilterDesc')}</p>
                      </div>
                      <Switch
                        checked={getBool('contentFilter', true)}
                        onCheckedChange={(v) => updateField('contentFilter', v)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <div>
                        <Label>{t('settings.security.contentReview')}</Label>
                        <p className="text-sm text-muted-foreground">{t('settings.security.contentReviewDesc')}</p>
                      </div>
                      <Switch
                        checked={getBool('contentReview', true)}
                        onCheckedChange={(v) => updateField('contentReview', v)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('settings.security.adminQQ')}</Label>
                      <Textarea
                        placeholder={t('settings.security.adminQQPlaceholder')}
                        value={getStr('adminQqList', '')}
                        onChange={(e) => updateField('adminQqList', e.target.value)}
                      />
                      <p className="text-sm text-muted-foreground">{t('settings.security.adminQQDesc')}</p>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="module" className="space-y-4">
            {/* 当前模式状态 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Cpu className="h-5 w-5" />
                  系统运行模式
                </CardTitle>
                <CardDescription>
                  切换训练/推理模式，优化资源管理并避免内存溢出
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {moduleStatus ? (
                  <>
                    {/* 当前模式指示器 */}
                    <div className="flex items-center justify-center gap-4 p-6 rounded-lg bg-muted/50">
                      <div className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all ${
                        moduleStatus.mode === 'training'
                          ? 'border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/20'
                          : 'border-muted bg-background'
                      }`}>
                        <BookOpen className={`h-8 w-8 ${moduleStatus.mode === 'training' ? 'text-blue-500' : 'text-muted-foreground'}`} />
                        <span className="font-semibold">训练与预处理</span>
                        <span className="text-xs text-muted-foreground">API生成 / LoRA训练 / RAG构建</span>
                      </div>
                      <ArrowRightLeft className="h-6 w-6 text-muted-foreground" />
                      <div className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all ${
                        moduleStatus.mode === 'inference'
                          ? 'border-purple-500 bg-purple-500/10 shadow-lg shadow-purple-500/20'
                          : 'border-muted bg-background'
                      }`}>
                        <Zap className={`h-8 w-8 ${moduleStatus.mode === 'inference' ? 'text-purple-500' : 'text-muted-foreground'}`} />
                        <span className="font-semibold">推理与部署</span>
                        <span className="text-xs text-muted-foreground">本地模型 / LoRA加载 / RAG检索</span>
                      </div>
                    </div>

                    {/* 内存使用 */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground flex items-center gap-1">
                            <MemoryStick className="h-4 w-4" /> 系统内存
                          </span>
                          <span>{moduleStatus.memory.used_gb.toFixed(1)} / {moduleStatus.memory.total_gb.toFixed(1)} GB</span>
                        </div>
                        <div className="h-2 rounded-full bg-muted overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              moduleStatus.memory.percent > 80 ? 'bg-red-500' : moduleStatus.memory.percent > 60 ? 'bg-yellow-500' : 'bg-green-500'
                            }`}
                            style={{ width: `${Math.min(moduleStatus.memory.percent, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">{moduleStatus.memory.percent.toFixed(1)}% 使用</span>
                      </div>
                      {moduleStatus.memory.gpu_total_gb > 0 && (
                        <div className="space-y-2">
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-muted-foreground flex items-center gap-1">
                              <Cpu className="h-4 w-4" /> GPU 显存
                            </span>
                            <span>{moduleStatus.memory.gpu_used_gb.toFixed(1)} / {moduleStatus.memory.gpu_total_gb.toFixed(1)} GB</span>
                          </div>
                          <div className="h-2 rounded-full bg-muted overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all ${
                                moduleStatus.memory.gpu_percent > 80 ? 'bg-red-500' : moduleStatus.memory.gpu_percent > 60 ? 'bg-yellow-500' : 'bg-green-500'
                              }`}
                              style={{ width: `${Math.min(moduleStatus.memory.gpu_percent, 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-muted-foreground">{moduleStatus.memory.gpu_percent.toFixed(1)}% 使用</span>
                        </div>
                      )}
                    </div>

                    {/* 模式信息 */}
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">当前模式</span>
                        <span className="font-medium">{moduleStatus.mode === 'training' ? '训练与预处理' : '推理与部署'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">推理模型</span>
                        <span className="font-medium">{moduleStatus.inference_model_loaded ? moduleStatus.inference_model_name : '未加载'}</span>
                      </div>
                      {moduleStatus.active_lora && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">活跃 LoRA</span>
                          <span className="font-medium">{moduleStatus.active_lora.split('/').pop() || moduleStatus.active_lora}</span>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">可切换到推理</span>
                        <span className={`font-medium ${moduleStatus.can_switch_to_inference ? 'text-green-500' : 'text-red-500'}`}>
                          {moduleStatus.can_switch_to_inference ? '是' : `否 - ${moduleStatus.can_switch_reason}`}
                        </span>
                      </div>
                    </div>

                    {/* 切换按钮 */}
                    <div className="flex gap-3">
                      <Button
                        className="flex-1"
                        variant={moduleStatus.mode === 'training' ? 'default' : 'outline'}
                        disabled={moduleStatus.mode === 'training' || switching}
                        onClick={async () => {
                          setSwitching(true);
                          try {
                            const result = await api.switchModuleMode('training');
                            if (result.success) {
                              toast.success(result.message);
                            } else {
                              toast.error(result.message);
                            }
                            setModuleStatus(await api.getModuleStatus());
                          } catch {
                            toast.error('切换失败');
                          } finally {
                            setSwitching(false);
                          }
                        }}
                      >
                        {switching ? '切换中...' : (
                          <><BookOpen className="mr-2 h-4 w-4" />切换到训练模式</>
                        )}
                      </Button>
                      <Button
                        className="flex-1"
                        variant={moduleStatus.mode === 'inference' ? 'default' : 'outline'}
                        disabled={moduleStatus.mode === 'inference' || switching || !moduleStatus.can_switch_to_inference}
                        onClick={async () => {
                          setSwitching(true);
                          try {
                            const result = await api.switchModuleMode('inference');
                            if (result.success) {
                              toast.success(`${result.message} (耗时${result.switch_time_ms}ms, 释放${result.memory_freed_gb}GB)`);
                            } else {
                              toast.error(result.message);
                            }
                            setModuleStatus(await api.getModuleStatus());
                          } catch {
                            toast.error('切换失败');
                          } finally {
                            setSwitching(false);
                          }
                        }}
                      >
                        {switching ? '切换中...' : (
                          <><Zap className="mr-2 h-4 w-4" />切换到推理模式</>
                        )}
                      </Button>
                    </div>

                    {/* 内存回收 */}
                    <Button
                      variant="ghost"
                      className="w-full"
                      onClick={async () => {
                        try {
                          const result = await api.forceGC();
                          toast.success(`已释放 ${result.memory_freed_gb}GB 内存`);
                          setModuleStatus(await api.getModuleStatus());
                        } catch {
                          toast.error('内存回收失败');
                        }
                      }}
                    >
                      <MemoryStick className="mr-2 h-4 w-4" />
                      手动回收内存
                    </Button>
                  </>
                ) : (
                  <div className="flex items-center justify-center py-8">
                    <Skeleton className="h-40 w-full" />
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 模式说明 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">模式说明</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div className="space-y-2">
                  <h4 className="font-medium flex items-center gap-2"><BookOpen className="h-4 w-4 text-blue-500" />训练与预处理模式</h4>
                  <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-2">
                    <li>使用 API 生成对话数据，不加载本地模型</li>
                    <li>LoRA 训练、数据集预处理、知识库构建</li>
                    <li>内存占用低，适合长时间训练任务</li>
                    <li>需要配置 DeepSeek API 或其他 OpenAI 兼容 API</li>
                  </ul>
                </div>
                <div className="space-y-2">
                  <h4 className="font-medium flex items-center gap-2"><Zap className="h-4 w-4 text-purple-500" />推理与部署模式</h4>
                  <ul className="list-disc list-inside text-muted-foreground space-y-1 ml-2">
                    <li>加载本地 7B 模型（4-bit 量化约 5GB 显存）</li>
                    <li>支持 LoRA 动态加载和 RAG 检索增强</li>
                    <li>内存占用高，需要 GPU 和足够系统内存</li>
                    <li>内置内存保护，超阈值自动拒绝请求</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

        </Tabs>

        <div className="flex items-center justify-between">
          {Object.keys(config).length > 0 && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              {t('settings.loaded')} {Object.keys(config).length} {t('settings.items')}
            </div>
          )}
          <Button onClick={handleSave} disabled={saving || loading} className="ml-auto">
            <Save className="mr-2 h-4 w-4" />
            {saving ? t('settings.saving') : t('settings.save')}
          </Button>
        </div>
      </div>
    </AppLayout>
  );
}
