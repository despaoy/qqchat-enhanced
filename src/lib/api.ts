/**
 * API 客户端模块
 *
 * 封装所有与后端 FastAPI 服务的通信接口，通过 Next.js API Route 代理转发请求。
 * 提供统一的类型定义和 ApiClient 类，涵盖健康检查、统计数据、消息记录、
 * LoRA 模型管理、训练任务管理、知识库管理等所有后端 API 调用。
 *
 * @module api
 * @example
 * import { api } from '@/lib/api';
 * const stats = await api.getStats();
 */

const API_BASE_URL = '/api';

/**
 * 从 localStorage 获取 JWT token，构建 Authorization header
 */
function getAuthHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem('qq_assistant_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

/** 系统统计响应 - 包含今日回复数、响应时间、活跃会话、资源使用等指标 */
export interface StatsResponse {
  todayReplies: number;
  avgResponseTime: number;
  activeSessions: number;
  modelLoad: number;
  cpuUsage: number;
  gpuMemory: {
    used: number;
    total: number;
  };
  memoryUsage: {
    used: number;
    total: number;
  };
  diskUsage: {
    used: number;
    total: number;
  };
}

/** 消息记录 - 记录一次完整的对话交互（用户消息 + 机器人回复） */
export interface Message {
  id: string;
  sessionType: 'group' | 'private';
  sessionId: string;
  sessionName: string;
  userId: string;
  userName: string;
  message: string;
  reply: string;
  modelName: string;
  loraName: string;
  costTime: number;
  createdAt: string;
}

/** 消息列表分页响应 */
export interface MessagesResponse {
  messages: Message[];
  total: number;
  total_all: number;
}

/** 会话摘要 */
export interface SessionSummary {
  sessionId: string;
  sessionType: 'group' | 'private';
  sessionName: string;
  messageCount: number;
  lastActive: string;
  summary: string;
  botEnabled: boolean;
}

/** 会话列表响应 */
export interface SessionsResponse {
  sessions: SessionSummary[];
}

/** LoRA 微调模型 - 个性化风格定制模型 */
export interface LoraModel {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'inactive';
  style: string;
  size: string;
  trainedSteps: number;
  totalSteps: number;
  createdAt: string;
}

/** LoRA 模型列表响应 */
export interface LorasResponse {
  loras: LoraModel[];
  total: number;
}

/** 健康检查响应 */
export interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  timestamp: string;
}

/** 消息生成请求参数 */
export interface GenerateRequest {
  message: string;
  sessionType?: string;
  sessionId?: string;
  userId?: string;
  userName?: string;
  loraName?: string;
}

/** 消息生成响应 */
export interface GenerateResponse {
  reply: string;
  model: string;
  costTime: number;
}

/** 单个时间点的活动统计数据 */
export interface ActivityData {
  time: string;
  messages: number;
  replies: number;
}

/** 活动趋势响应 - 24小时内的消息与回复趋势 */
export interface ActivityResponse {
  activity: ActivityData[];
}

/** 单个服务的运行状态 */
export interface ServiceStatus {
  name: string;
  status: 'running' | 'stopped' | 'connecting';
  uptime: string;
}

/** 服务状态列表响应 */
export interface ServicesResponse {
  services: ServiceStatus[];
}

/** 训练数据集信息 */
export interface Dataset {
  name: string;
  path: string;
  stats: {
    total?: number;
    train?: number;
    eval?: number;
  };
}

/** 数据集列表响应 */
export interface DatasetsResponse {
  success: boolean;
  datasets: Dataset[];
}

/** 模型训练配置 - 针对不同 GPU 的优化参数 */
export interface ModelConfig {
  name: string;
  model_name: string;
  gpu_type: string;
  batch_size: number;
  gradient_accumulation_steps: number;
  cutoff_len: number;
  lora_rank: number;
  lora_alpha: number;
  lora_dropout: number;
  learning_rate: number;
  num_train_epochs: number;
  warmup_ratio: number;
  weight_decay: number;
  bf16: boolean;
  fp16: boolean;
  load_in_4bit: boolean;
  use_gradient_checkpointing: boolean;
  description: string;
}

/** 模型配置列表响应 */
export interface ModelConfigsResponse {
  success: boolean;
  configs: ModelConfig[];
}

/** 训练任务 - 包含任务 ID、状态、进度等信息 */
export interface TrainingTask {
  task_id: string;
  lora_name: string;
  status: 'pending' | 'training' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  created_at: string;
  updated_at?: string;
  error_message?: string;
  config?: Record<string, unknown>;
}

/** 训练任务列表响应 */
export interface TrainingTasksResponse {
  success: boolean;
  tasks: TrainingTask[];
}

/** 单个训练任务响应 */
export interface TrainingTaskResponse {
  success: boolean;
  task: TrainingTask;
}

/** 人物风格预设 */
export interface CharacterStyle {
  name: string;
  display_name: string;
  description: string;
}

/** 风格列表响应 */
export interface StylesResponse {
  success: boolean;
  styles: CharacterStyle[];
}

/** 创建数据集请求参数 */
export interface CreateDatasetRequest {
  dataset_name: string;
  style?: string;
  custom_prompt?: string;
  data: unknown[];
}

/** 启动训练请求参数 */
export interface StartTrainingRequest {
  lora_name: string;
  dataset_name: string;
  model_type?: string;
  custom_config?: Record<string, unknown>;
}

/** 对话生成请求 */
export interface DialogueGenerateRequest {
  character_description: string;
  num_dialogues?: number;
  style?: string;
  custom_prompt?: string;
}

/** 单条对话 */
export interface DialogueConversation {
  conversations: Array<{
    from: 'human' | 'gpt';
    value: string;
  }>;
  system?: string;
  scene?: string;
  tags?: string[];
}

/** 对话生成响应 */
export interface DialogueGenerateResponse {
  success: boolean;
  dialogues: DialogueConversation[];
  total: number;
  cost_time: number;
  cancelled?: boolean;
}

/** 对话生成进度 */
export interface DialogueGenerationProgress {
  is_generating: boolean;
  cancel_requested: boolean;
  progress: number;
  total: number;
  batch_num: number;
  total_batches: number;
  generated_count: number;
  started_at: number | null;
  /** 本批次新增的对话，实时推送到前端 */
  new_dialogues: DialogueConversation[];
  /** 所有已生成的对话（持久累积，用于断线重连恢复） */
  all_generated_dialogues: DialogueConversation[];
}

/** 知识库文档 */
export interface KnowledgeDocument {
  id: number;
  title: string;
  content: string;
  category: string;
  knowledge_base_id: number | null;
  folder_id: number | null;
  sourceType: string;
  sourceUrl?: string;
  fileType?: string;
  fileSize?: number;
  chunkCount: number;
  createdAt: string;
  updatedAt: string;
}

/** 知识库文档分块 */
export interface KnowledgeChunk {
  id: number;
  documentId: number;
  chunkIndex: number;
  content: string;
  embedding?: number[];
  createdAt: string;
}

/** 知识库（顶层容器） */
export interface KnowledgeBase {
  id: number;
  name: string;
  description: string;
  documentCount: number;
  folderCount: number;
  created_at: string;
  updated_at: string;
}

/** 知识库文件夹 */
export interface KnowledgeFolder {
  id: number;
  knowledge_base_id: number;
  name: string;
  description: string;
  documentCount: number;
  created_at: string;
  updated_at: string;
}

/** ZIP上传响应 */
export interface ZipUploadResponse {
  success: boolean;
  message: string;
  createdFolders: string[];
  createdDocs: number;
  errors: string[];
}

/** 扫描目录树节点 */
export interface ScanDirectory {
  name: string;
  type: 'folder' | 'file';
  children?: ScanDirectory[];
  fileCount?: number;
  totalSize?: number;
  size?: number;
  extension?: string;
}

/** 知识库搜索结果项 - 包含相关性评分 */
export interface KnowledgeSearchResult {
  documentId: number;
  documentTitle: string;
  chunkId: number;
  chunkIndex: number;
  content: string;
  score: number;
}

/** 知识库统计数据 */
export interface KnowledgeStats {
  totalDocuments: number;
  totalChunks: number;
  totalCharacters: number;
}

/** 知识库文档列表响应 */
export interface KnowledgeDocumentsResponse {
  success: boolean;
  documents: KnowledgeDocument[];
  stats: KnowledgeStats;
}

/** 单个知识库文档响应 */
export interface KnowledgeDocumentResponse {
  success: boolean;
  document: KnowledgeDocument;
  chunks: KnowledgeChunk[];
}

/** 创建知识库文档请求参数 */
export interface KnowledgeCreateRequest {
  title: string;
  content: string;
  category?: string;
  knowledge_base_id?: number | null;
  folder_id?: number | null;
  sourceType?: string;
  sourceUrl?: string;
  fileType?: string;
  fileSize?: number;
}

/** 更新知识库文档请求参数 */
export interface KnowledgeUpdateRequest {
  title?: string;
  content?: string;
  category?: string;
  knowledge_base_id?: number | null;
  folder_id?: number | null;
  sourceType?: string;
  sourceUrl?: string;
  fileType?: string;
  fileSize?: number;
}

/** 知识库搜索请求参数 */
export interface KnowledgeSearchRequest {
  query: string;
  topK?: number;
}

/** 知识库搜索响应 */
export interface KnowledgeSearchResponse {
  success: boolean;
  query: string;
  results: KnowledgeSearchResult[];
}

/** 知识库统计响应 */
export interface KnowledgeStatsResponse {
  success: boolean;
  stats: KnowledgeStats;
}

/** 系统配置 - 键值对结构，值类型为 string | number | boolean */
export interface SystemConfig {
  [key: string]: string | number | boolean;
}

/** 用户信息 */
export interface User {
  id: number;
  username: string;
  created_at: string;
}

/** 注册请求 */
export interface RegisterRequest {
  username: string;
  password: string;
}

/** 登录请求 */
export interface LoginRequest {
  username: string;
  password: string;
}

/** 配置获取响应 */
export interface ConfigResponse {
  config: SystemConfig;
}

/** 配置更新响应 */
export interface ConfigUpdateResponse {
  success: boolean;
  message: string;
  config: SystemConfig;
}

/** 可用模型信息 */
export interface AvailableModel {
  name: string;
  display_name: string;
  repo_id: string;
  size: string;
  description: string;
  downloaded: boolean;
}

/** 模型列表响应 */
export interface ModelsResponse {
  success: boolean;
  models: AvailableModel[];
}

/** 已保存对话列表项 */
export interface SavedDialogueItem {
  id: number;
  name: string;
  character_desc: string;
  style: string | null;
  dialogue_count: number;
  created_at: string;
  updated_at: string;
}

/** 已保存对话完整数据 */
export interface SavedDialogueFull {
  success: boolean;
  id: number;
  name: string;
  character_desc: string;
  style: string | null;
  dialogue_count: number;
  dialogues: DialogueConversation[];
  turn_stats: Record<string, number> | null;
  scene_stats: Record<string, number> | null;
  created_at: string;
  updated_at: string;
}

/** 保存对话请求 */
export interface SaveDialoguesRequest {
  name: string;
  character_desc: string;
  style?: string;
  dialogues: DialogueConversation[];
  turn_stats?: Record<string, number>;
  scene_stats?: Record<string, number>;
}

// ============================================
// 模块管理类型
// ============================================

export interface ModuleMemoryInfo {
  total_gb: number;
  available_gb: number;
  used_gb: number;
  percent: number;
}

export interface ModuleGpuInfo {
  total_gb: number;
  used_gb: number;
  available_gb: number;
  percent: number;
}

export interface ModuleStatusResponse {
  mode: 'training' | 'inference';
  memory: ModuleMemoryInfo & { gpu_total_gb: number; gpu_used_gb: number; gpu_available_gb: number; gpu_percent: number };
  inference_model_loaded: boolean;
  inference_model_name: string;
  active_lora: string;
  training_active: boolean;
  generation_active: boolean;
  uptime_seconds: number;
  can_switch_to_inference: boolean;
  can_switch_reason: string;
}

export interface SwitchModeResponse {
  success: boolean;
  from_mode: string;
  to_mode: string;
  switch_time_ms: number;
  memory_freed_gb: number;
  message: string;
  errors: string[];
}

export interface MemoryInfoResponse {
  system: ModuleMemoryInfo;
  gpu: ModuleGpuInfo | null;
  safety: {
    is_safe: boolean;
    can_load_inference_model: boolean;
    reason: string;
  };
}

/**
 * API 客户端类
 *
 * 封装对后端 FastAPI 服务的所有 HTTP 请求，提供类型安全的接口调用。
 * 导出为单例实例 `api`，全局共享使用。
 */
class ApiClient {
  /**
   * 通用请求方法 - 封装 fetch 调用，统一处理请求头和错误
   * @param {string} path - API 路径（相对于 /api）
   * @param {RequestInit} [options] - fetch 选项
   * @returns {Promise<T>} 解析后的 JSON 响应
   */
  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
  }

  /**
   * 批量删除消息（基于筛选条件）
   */
  async deleteMessagesBatch(filters: { search?: string; sessionType?: string; lora?: string; sessionName?: string }): Promise<{ success: boolean; deleted: number; message: string }> {
    const response = await fetch(`${API_BASE_URL}/messages/batch`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filters),
    });
    if (!response.ok) {
      throw new Error('Failed to delete messages batch');
    }
    return response.json();
  }

  /**
   * 健康检查 - 检测后端服务是否正常运行
   * @returns {Promise<HealthResponse>} 服务健康状态及时间戳
   */
  async health(): Promise<HealthResponse> {
    const response = await fetch(`${API_BASE_URL.replace('/api', '')}/health`);
    if (!response.ok) {
      throw new Error('Health check failed');
    }
    return response.json();
  }

  /**
   * 获取系统统计数据
   * @returns {Promise<StatsResponse>} 包含今日回复数、响应时间、活跃会话、CPU/内存/GPU 等指标
   */
  async getStats(): Promise<StatsResponse> {
    const response = await fetch(`${API_BASE_URL}/stats`);
    if (!response.ok) {
      throw new Error('Failed to fetch stats');
    }
    return response.json();
  }

  /**
   * 获取消息记录（分页）
   * @param {number} [limit] - 返回条数限制
   * @param {number} [offset] - 分页偏移量
   * @returns {Promise<MessagesResponse>} 消息列表及总数
   */
  async getMessages(limit?: number, offset?: number): Promise<MessagesResponse> {
    const params = new URLSearchParams();
    if (limit) params.append('limit', limit.toString());
    if (offset) params.append('offset', offset.toString());
    
    const url = `${API_BASE_URL}/messages${params.toString() ? '?' + params.toString() : ''}`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error('Failed to fetch messages');
    }
    return response.json();
  }

  /**
   * 删除单条消息记录
   * @param {string} id - 消息 ID
   */
  async deleteMessage(id: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/messages/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete message');
    }
    return response.json();
  }

  /**
   * 获取会话列表（聚合统计）
   */
  async getSessionSummaries(): Promise<SessionsResponse> {
    const response = await fetch(`${API_BASE_URL}/sessions`);
    if (!response.ok) {
      throw new Error('Failed to fetch sessions');
    }
    return response.json();
  }

  /**
   * 设置会话机器人开关
   */
  async toggleSessionBot(sessionId: string, enabled: boolean): Promise<{ success: boolean; sessionId: string; botEnabled: boolean }> {
    const response = await fetch(`${API_BASE_URL}/sessions/bot-toggle`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, enabled }),
    });
    if (!response.ok) {
      throw new Error('Failed to toggle session bot');
    }
    return response.json();
  }

  /**
   * 获取 LoRA 模型列表
   * @returns {Promise<LorasResponse>} LoRA 模型列表及总数
   */
  async getLoras(): Promise<LorasResponse> {
    const response = await fetch(`${API_BASE_URL}/loras`);
    if (!response.ok) {
      throw new Error('Failed to fetch loras');
    }
    const data = await response.json();
    return {
      loras: data.loras,
      total: data.loras.length
    };
  }

  /**
   * 切换 LoRA 模型的激活状态
   * @param {string} id - LoRA 模型 ID
   * @param {string} currentStatus - 当前状态（active 或 inactive）
   * @returns {Promise<LoraModel>} 更新后的 LoRA 模型信息
   */
  async toggleLoraStatus(id: string, currentStatus: string): Promise<LoraModel> {
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
    const response = await fetch(`${API_BASE_URL}/loras/${id}/status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ status: newStatus }),
    });
    if (!response.ok) {
      throw new Error('Failed to toggle lora status');
    }
    const result = await response.json();
    return result.lora;
  }

  /**
   * 删除 LoRA 模型
   * @param {string} id - 要删除的 LoRA 模型 ID
   * @returns {Promise<{success: boolean; message: string}>} 删除结果
   */
  async deleteLora(id: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/loras/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete lora');
    }
    return response.json();
  }

  /**
   * 扫描 loras 目录，自动发现并注册新的 LoRA 适配器
   */
  async scanLoras(): Promise<{ success: boolean; message: string; new_count: number }> {
    const response = await fetch(`${API_BASE_URL}/loras/scan`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('扫描LoRA失败');
    }
    return response.json();
  }

  /**
   * 测试消息生成 - 向机器人发送消息并获取回复
   * @param {GenerateRequest} request - 消息内容、会话类型、用户信息
   * @returns {Promise<GenerateResponse>} 机器人回复内容及耗时
   */
  async generateReply(request: GenerateRequest): Promise<GenerateResponse> {
    const response = await fetch(`${API_BASE_URL}/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      throw new Error('Failed to generate reply');
    }
    return response.json();
  }

  /**
   * 获取 24 小时活动趋势数据
   * @returns {Promise<ActivityResponse>} 每小时的接收消息数和回复消息数
   */
  async getActivity(): Promise<ActivityResponse> {
    const response = await fetch(`${API_BASE_URL}/stats/activity`);
    if (!response.ok) {
      throw new Error('Failed to fetch activity');
    }
    return response.json();
  }

  /**
   * 获取各服务运行状态
   * @returns {Promise<ServicesResponse>} 各服务名称、状态、运行时长
   */
  async getServices(): Promise<ServicesResponse> {
    const response = await fetch(`${API_BASE_URL}/stats/services`);
    if (!response.ok) {
      throw new Error('Failed to fetch services');
    }
    return response.json();
  }


  /**
   * 列出所有训练数据集
   * @returns {Promise<DatasetsResponse>} 数据集列表
   */
  async listDatasets(): Promise<DatasetsResponse> {
    const response = await fetch(`${API_BASE_URL}/training/datasets`);
    if (!response.ok) {
      throw new Error('Failed to fetch datasets');
    }
    return response.json();
  }

  /**
   * 创建训练数据集
   * @param {CreateDatasetRequest} request - 数据集名称、风格、自定义提示和原始数据
   * @returns {Promise<{success: boolean; message: string; dataset_name: string}>} 创建结果
   */
  async createDataset(request: CreateDatasetRequest): Promise<{ success: boolean; message: string; dataset_name: string }> {
    const response = await fetch(`${API_BASE_URL}/training/datasets`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      throw new Error('Failed to create dataset');
    }
    return response.json();
  }

  /**
   * 列出可用的模型训练配置（支持 RTX 4060 / RTX 3090 等多种 GPU）
   * @returns {Promise<ModelConfigsResponse>} GPU 优化训练配置列表
   */
  async listModelConfigs(): Promise<ModelConfigsResponse> {
    const response = await fetch(`${API_BASE_URL}/training/models`);
    if (!response.ok) {
      throw new Error('Failed to fetch model configs');
    }
    return response.json();
  }

  /**
   * 导出数据集为 ZIP 文件（用于上传到服务器训练）
   * @param {string} datasetName - 数据集名称
   * @returns {Promise<Response>} ZIP 文件的 Response 对象
   */
  async exportDataset(datasetName: string): Promise<Response> {
    const response = await fetch(`${API_BASE_URL}/training/datasets/${encodeURIComponent(datasetName)}/export`);
    return response;
  }

  /**
   * 扫描数据集文件夹
   * @param folder 要扫描的文件夹路径，为空时使用默认目录
   */
  async scanDatasets(folder?: string): Promise<{ success: boolean; scan_path: string; datasets: Array<{ name: string; path: string; file_count: number; files: string[]; valid: boolean }>; count: number }> {
    const params = folder ? `?folder=${encodeURIComponent(folder)}` : '';
    const response = await fetch(`${API_BASE_URL}/training/datasets/scan${params}`);
    if (!response.ok) {
      throw new Error('Failed to scan datasets');
    }
    return response.json();
  }

  /**
   * 从扫描结果导入数据集
   */
  async importDataset(sourcePath: string, datasetName?: string): Promise<{ success: boolean; name: string; path: string; stats: { total: number; train: number; eval: number } }> {
    const response = await fetch(`${API_BASE_URL}/training/datasets/scan/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_path: sourcePath, dataset_name: datasetName }),
    });
    if (!response.ok) {
      throw new Error('Failed to import dataset');
    }
    return response.json();
  }

  /**
   * 启动 LoRA 训练任务
   * @param {StartTrainingRequest} request - LoRA 名称、数据集名称、模型类型、自定义配置
   * @returns {Promise<{success: boolean; task_id: string; message: string}>} 启动的训练任务信息
   */
  async startTraining(request: StartTrainingRequest): Promise<{ success: boolean; task_id: string; message: string }> {
    const response = await fetch(`${API_BASE_URL}/training/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    const data = await response.json();
    if (!response.ok) {
      const msg = data.message || data.detail || '启动训练失败';
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    return data;
  }

  /**
   * 列出所有训练任务
   * @returns {Promise<TrainingTasksResponse>} 训练任务列表
   */
  async listTrainingTasks(): Promise<TrainingTasksResponse> {
    const response = await fetch(`${API_BASE_URL}/training/tasks`);
    if (!response.ok) {
      throw new Error('Failed to fetch training tasks');
    }
    return response.json();
  }

  /**
   * 获取单个训练任务的详细信息
   * @param {string} taskId - 训练任务 ID
   * @returns {Promise<TrainingTaskResponse>} 任务详情（状态、进度等）
   */
  async getTrainingTask(taskId: string): Promise<TrainingTaskResponse> {
    const response = await fetch(`${API_BASE_URL}/training/tasks/${taskId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch training task');
    }
    return response.json();
  }

  /**
   * 取消正在运行的训练任务
   * @param {string} taskId - 训练任务 ID
   * @returns {Promise<{success: boolean; message: string}>} 取消结果
   */
  async cancelTrainingTask(taskId: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/training/tasks/${taskId}/cancel`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to cancel training task');
    }
    return response.json();
  }

  /**
   * 列出可用的预定义人物风格
   * @returns {Promise<StylesResponse>} 风格列表
   */
  async listStyles(): Promise<StylesResponse> {
    const response = await fetch(`${API_BASE_URL}/training/styles`);
    if (!response.ok) {
      throw new Error('Failed to fetch styles');
    }
    return response.json();
  }

  /**
   * 获取知识库文档列表（分页）
   * @param {number} [limit] - 返回条数限制
   * @param {number} [offset] - 分页偏移量
   * @returns {Promise<KnowledgeDocumentsResponse>} 文档列表及统计信息
   */
  async getKnowledgeDocuments(limit?: number, offset?: number, category?: string, knowledgeBaseId?: number, folderId?: number): Promise<KnowledgeDocumentsResponse> {
    const params = new URLSearchParams();
    if (limit) params.append('limit', limit.toString());
    if (offset) params.append('offset', offset.toString());
    if (category && category !== '全部') params.append('category', category);
    if (knowledgeBaseId) params.append('knowledge_base_id', knowledgeBaseId.toString());
    if (folderId) params.append('folder_id', folderId.toString());
    
    const url = `${API_BASE_URL}/knowledge/documents${params.toString() ? '?' + params.toString() : ''}`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error('Failed to fetch knowledge documents');
    }
    return response.json();
  }

  /**
   * 获取单个知识库文档及其分块
   * @param {number} docId - 文档 ID
   * @returns {Promise<KnowledgeDocumentResponse>} 文档详情及内容分块
   */
  async getKnowledgeDocument(docId: number): Promise<KnowledgeDocumentResponse> {
    const response = await fetch(`${API_BASE_URL}/knowledge/documents/${docId}`);
    if (!response.ok) {
      throw new Error('Failed to fetch knowledge document');
    }
    return response.json();
  }

  /**
   * 创建知识库文档（自动分块和向量化）
   * @param {KnowledgeCreateRequest} request - 文档标题、内容、来源类型等
   * @returns {Promise<{success: boolean; document: KnowledgeDocument}>} 创建结果
   */
  async createKnowledgeDocument(request: KnowledgeCreateRequest): Promise<{ success: boolean; document: KnowledgeDocument }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/documents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      throw new Error('Failed to create knowledge document');
    }
    return response.json();
  }

  /**
   * 更新知识库文档
   * @param {number} docId - 文档 ID
   * @param {KnowledgeUpdateRequest} request - 需要更新的字段
   * @returns {Promise<{success: boolean; document: KnowledgeDocument}>} 更新结果
   */
  async updateKnowledgeDocument(docId: number, request: KnowledgeUpdateRequest): Promise<{ success: boolean; document: KnowledgeDocument }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/documents/${docId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      throw new Error('Failed to update knowledge document');
    }
    return response.json();
  }

  /**
   * 删除知识库文档及其所有分块
   * @param {number} docId - 文档 ID
   * @returns {Promise<{success: boolean; message: string}>} 删除结果
   */
  async deleteKnowledgeDocument(docId: number): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/documents/${docId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete knowledge document');
    }
    return response.json();
  }

  /**
   * 知识库语义搜索 - 结合向量检索和关键词匹配
   * @param {KnowledgeSearchRequest} request - 搜索关键词和返回条数
   * @returns {Promise<KnowledgeSearchResponse>} 按照相关性排序的搜索结果
   */
  async searchKnowledge(request: KnowledgeSearchRequest): Promise<KnowledgeSearchResponse> {
    const response = await fetch(`${API_BASE_URL}/knowledge/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      throw new Error('Failed to search knowledge');
    }
    return response.json();
  }

  /**
   * 获取知识库统计数据
   * @returns {Promise<KnowledgeStatsResponse>} 文档总数、分块总数、总字符数
   */
  async getKnowledgeStats(): Promise<KnowledgeStatsResponse> {
    const response = await fetch(`${API_BASE_URL}/knowledge/stats`);
    if (!response.ok) {
      throw new Error('Failed to fetch knowledge stats');
    }
    return response.json();
  }

  // ============================================
  // 知识库管理 API
  // ============================================

  /** 获取所有知识库 */
  async getKnowledgeBases(): Promise<{ success: boolean; bases: KnowledgeBase[] }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/bases`);
    if (!response.ok) throw new Error('获取知识库列表失败');
    return response.json();
  }

  /** 创建知识库 */
  async createKnowledgeBase(name: string, description: string = ''): Promise<{ success: boolean; base: KnowledgeBase }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/bases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || '创建知识库失败');
    }
    return response.json();
  }

  /** 更新知识库 */
  async updateKnowledgeBase(kbId: number, data: { name?: string; description?: string }): Promise<{ success: boolean; base: KnowledgeBase }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/bases/${kbId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('更新知识库失败');
    return response.json();
  }

  /** 删除知识库 */
  async deleteKnowledgeBase(kbId: number): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/bases/${kbId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('删除知识库失败');
    return response.json();
  }

  /** 获取知识库下的文件夹 */
  async getKnowledgeFolders(kbId: number): Promise<{ success: boolean; folders: KnowledgeFolder[] }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/bases/${kbId}/folders`);
    if (!response.ok) throw new Error('获取文件夹列表失败');
    return response.json();
  }

  /** 创建文件夹 */
  async createKnowledgeFolder(kbId: number, name: string, description: string = ''): Promise<{ success: boolean; folder: KnowledgeFolder }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/bases/${kbId}/folders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || '创建文件夹失败');
    }
    return response.json();
  }

  /** 删除文件夹 */
  async deleteKnowledgeFolder(folderId: number): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/folders/${folderId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('删除文件夹失败');
    return response.json();
  }

  /** 上传ZIP文件到知识库 */
  async uploadKnowledgeZip(kbId: number, file: File): Promise<ZipUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE_URL}/knowledge/bases/${kbId}/upload-zip`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || '上传ZIP失败');
    }
    return response.json();
  }

  /** 扫描知识库文件夹目录 */
  async scanKnowledgeDirs(): Promise<{ success: boolean; directories: ScanDirectory[]; message?: string }> {
    const response = await fetch(`${API_BASE_URL}/knowledge/scan`);
    if (!response.ok) throw new Error('扫描知识库目录失败');
    return response.json();
  }

  /** 导入扫描到的目录 */
  async importScannedDir(directoryName: string, kbId?: number): Promise<ZipUploadResponse & { knowledgeBase?: KnowledgeBase }> {
    const params = new URLSearchParams();
    params.append('directory_name', directoryName);
    if (kbId) params.append('kb_id', kbId.toString());
    const response = await fetch(`${API_BASE_URL}/knowledge/scan/import?${params.toString()}`, {
      method: 'POST',
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || '导入目录失败');
    }
    return response.json();
  }

  /**
   * 获取系统配置
   * @returns {Promise<ConfigResponse>} 系统配置键值对
   */
  async getConfig(): Promise<ConfigResponse> {
    const response = await fetch(`${API_BASE_URL}/config`);
    if (!response.ok) {
      throw new Error('Failed to fetch config');
    }
    return response.json();
  }

  /**
   * 更新系统配置
   * @param {SystemConfig} config - 要更新的配置键值对
   * @returns {Promise<ConfigUpdateResponse>} 更新结果
   */
  async updateConfig(config: SystemConfig): Promise<ConfigUpdateResponse> {
    const response = await fetch(`${API_BASE_URL}/config`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });
    if (!response.ok) {
      throw new Error('Failed to update config');
    }
    return response.json();
  }

  /**
   * 获取可用模型列表
   * @returns {Promise<ModelsResponse>} 模型列表
   */
  async getModels(): Promise<ModelsResponse> {
    const response = await fetch(`${API_BASE_URL}/models`);
    if (!response.ok) {
      throw new Error('Failed to fetch models');
    }
    return response.json();
  }

  /**
   * 生成对话数据
   * @param {DialogueGenerateRequest} request - 角色描述、对话数量等
   * @returns {Promise<DialogueGenerateResponse>} 生成的对话数据
   */
  async generateDialogues(request: DialogueGenerateRequest, signal?: AbortSignal): Promise<DialogueGenerateResponse> {
    const response = await fetch(`${API_BASE_URL}/training/generate-dialogues`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      signal,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to generate dialogues' }));
      throw new Error(error.detail || 'Failed to generate dialogues');
    }
    return response.json();
  }

  /** 取消对话生成 */
  async cancelDialogueGeneration(): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/training/generate-dialogues/cancel`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('取消生成失败');
    return response.json();
  }

  /** 强制重置生成状态（用于断线重连后清理残留状态） */
  async forceResetGeneration(): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/training/generate-dialogues/force-reset`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('重置状态失败');
    return response.json();
  }

  /** 获取对话生成进度 */
  async getDialogueGenerationProgress(): Promise<DialogueGenerationProgress> {
    const response = await fetch(`${API_BASE_URL}/training/generate-dialogues/progress`);
    if (!response.ok) throw new Error('获取进度失败');
    return response.json();
  }

  /** 用户注册 */
  async register(request: RegisterRequest): Promise<{ success: boolean; user: User; token: string }> {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /** 用户登录 */
  async login(request: LoginRequest): Promise<{ success: boolean; user: User; token: string }> {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /** 获取当前用户信息（使用 JWT token） */
  async getCurrentUser(): Promise<{ success: boolean; user: User }> {
    return this.request('/auth/me', {
      headers: getAuthHeaders(),
    });
  }

  /** 保存用户表单数据（使用 JWT token） */
  async saveUserData(pageKey: string, dataJson: string): Promise<{ success: boolean; message: string }> {
    return this.request('/user/data', {
      method: 'PUT',
      headers: { ...getAuthHeaders() },
      body: JSON.stringify({ page_key: pageKey, data_json: dataJson }),
    });
  }

  /** 获取用户表单数据（使用 JWT token） */
  async getUserData(pageKey?: string): Promise<{ success: boolean; data: Record<string, { data_json: string; updated_at: string }> | { page_key: string; data_json: string; updated_at: string } | null }> {
    const params = new URLSearchParams();
    if (pageKey) params.set('page_key', pageKey);
    const qs = params.toString();
    return this.request(`/user/data${qs ? '?' + qs : ''}`, {
      headers: getAuthHeaders(),
    });
  }

  /** 保存对话数据 */
  async saveDialogues(request: SaveDialoguesRequest): Promise<{ success: boolean; id: number; message: string }> {
    const response = await fetch(`${API_BASE_URL}/training/saved-dialogues`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || err.error || '保存失败');
    }
    return response.json();
  }

  /** 列出所有已保存对话 */
  async listSavedDialogues(): Promise<{ success: boolean; items: SavedDialogueItem[] }> {
    const response = await fetch(`${API_BASE_URL}/training/saved-dialogues`);
    if (!response.ok) throw new Error('获取列表失败');
    return response.json();
  }

  /** 获取单条已保存对话 */
  async getSavedDialogue(id: number): Promise<SavedDialogueFull> {
    const response = await fetch(`${API_BASE_URL}/training/saved-dialogues/${id}`);
    if (!response.ok) throw new Error('获取对话失败');
    return response.json();
  }

  /** 删除已保存对话 */
  async deleteSavedDialogue(id: number): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/training/saved-dialogues/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('删除失败');
    return response.json();
  }

  // ── Claw 工具管理 ──

  /**
   * 列出所有 Claw 工具
   */
  async listClawTools(): Promise<{ success: boolean; tools: Array<{ name: string; description: string; code: string; enabled: boolean; builtin: boolean; created_at?: string; updated_at?: string }>; total: number }> {
    const response = await fetch(`${API_BASE_URL}/claw/tools`);
    if (!response.ok) throw new Error('获取工具列表失败');
    return response.json();
  }

  /**
   * 保存（创建/更新）Claw 工具
   */
  async saveClawTool(data: { name: string; description: string; code: string; enabled: boolean }): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/claw/tools`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('保存工具失败');
    return response.json();
  }

  /**
   * 删除 Claw 工具
   */
  async deleteClawTool(name: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE_URL}/claw/tools/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('删除工具失败');
    return response.json();
  }

  /**
   * 测试执行 Claw 工具代码
   */
  async executeClawTool(code: string, args?: Record<string, unknown>): Promise<{ success: boolean; output: string; error: string; result: string }> {
    const response = await fetch(`${API_BASE_URL}/claw/tools/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, args: args || {} }),
    });
    return response.json();
  }

  /** 从已保存对话中删除单条对话 */
  async deleteDialogueFromSaved(id: number, index: number): Promise<{ success: boolean; message: string; remaining_count: number }> {
    const response = await fetch(`${API_BASE_URL}/training/saved-dialogues/${id}/dialogues/${index}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('删除失败');
    return response.json();
  }

  /** 从已保存对话创建数据集 */
  async createDatasetFromSaved(id: number, datasetName?: string): Promise<{ success: boolean; dataset: Record<string, unknown> }> {
    const params = new URLSearchParams();
    if (datasetName) params.set('dataset_name', datasetName);
    const response = await fetch(`${API_BASE_URL}/training/saved-dialogues/${id}/create-dataset?${params.toString()}`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('创建数据集失败');
    return response.json();
  }

  // ============================================
  // 模块管理 API
  // ============================================

  /** 获取模块状态 */
  async getModuleStatus(): Promise<ModuleStatusResponse> {
    return this.request('/module/status');
  }

  /** 切换系统模式 */
  async switchModuleMode(targetMode: 'training' | 'inference'): Promise<SwitchModeResponse> {
    return this.request('/module/switch', {
      method: 'POST',
      body: JSON.stringify({ target_mode: targetMode }),
    });
  }

  /** 获取内存信息 */
  async getMemoryInfo(): Promise<MemoryInfoResponse> {
    return this.request('/module/memory');
  }

  /** 强制垃圾回收 */
  async forceGC(): Promise<{ success: boolean; memory_freed_gb: number; before: { used_gb: number; percent: number }; after: { used_gb: number; percent: number } }> {
    return this.request('/module/gc', { method: 'POST' });
  }
}

// 导出单例实例
export const api = new ApiClient();

export default api;
