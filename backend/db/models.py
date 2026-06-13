"""
Pydantic 请求/响应模型
从 main.py 提取，集中管理所有 API 数据模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

# ============================================
# 核心消息模型
# ============================================


class MessageRequest(BaseModel):
    message: str
    sessionType: str = "private"
    sessionId: str = ""
    userId: str = ""
    userName: str = ""
    loraName: str = ""


class GenerateResponse(BaseModel):
    reply: str
    model: str = "Qwen/Qwen2.5-7B-Instruct"
    costTime: float


class StatsResponse(BaseModel):
    todayReplies: int = 0
    avgResponseTime: float = 0.0
    activeSessions: int = 0
    modelLoad: int = 0
    cpuUsage: int = 0
    gpuMemory: Dict[str, float] = {}
    memoryUsage: Dict[str, float] = {}
    diskUsage: Dict[str, float] = {}


# ============================================
# LoRA 训练管理模型
# ============================================


class DatasetUploadRequest(BaseModel):
    """数据集上传请求"""
    dataset_name: str
    style: Optional[str] = None
    custom_prompt: Optional[str] = None
    data: List[Dict[str, Any]]


class TrainingStartRequest(BaseModel):
    """训练启动请求"""
    lora_name: str
    dataset_name: str
    model_type: str = "qwen2.5-7b"
    custom_config: Optional[Dict[str, Any]] = None


class ModelDownloadRequest(BaseModel):
    """模型下载请求"""
    model_name: str
    force: bool = False


# ============================================
# 知识库管理模型
# ============================================


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = None
    description: Optional[str] = None


class KnowledgeFolderCreate(BaseModel):
    """创建知识库文件夹请求"""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""


class KnowledgeDocumentCreate(BaseModel):
    """创建知识库文档请求"""
    title: str
    content: str
    category: str = "未分类"
    knowledge_base_id: Optional[int] = None
    folder_id: Optional[int] = None
    sourceType: str = "text"
    sourceUrl: Optional[str] = None
    fileType: Optional[str] = None
    fileSize: Optional[int] = None


class KnowledgeDocumentUpdate(BaseModel):
    """更新知识库文档请求"""
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    knowledge_base_id: Optional[int] = None
    folder_id: Optional[int] = None
    sourceType: Optional[str] = None
    sourceUrl: Optional[str] = None
    fileType: Optional[str] = None
    fileSize: Optional[int] = None


class KnowledgeSearchRequest(BaseModel):
    """知识库搜索请求"""
    query: str
    topK: int = 5


class KnowledgeSearchResult(BaseModel):
    """知识库搜索结果"""
    documentId: int
    documentTitle: str
    chunkId: int
    chunkIndex: int
    content: str
    score: float


# ============================================
# 用户认证模型
# ============================================


class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)


class LoginRequest(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class UserDataRequest(BaseModel):
    """用户数据保存请求"""
    page_key: str = Field(..., min_length=1, max_length=100)
    data_json: str = Field(..., min_length=1)


# ============================================
# 对话数据保存模型
# ============================================


class SaveDialoguesRequest(BaseModel):
    """保存对话数据请求"""
    name: str = Field(..., min_length=1, max_length=200)
    character_desc: str = Field(..., min_length=1)
    style: Optional[str] = None
    dialogues: list
    turn_stats: Optional[Dict[str, int]] = None
    scene_stats: Optional[Dict[str, int]] = None


class SavedDialoguesListItem(BaseModel):
    """已保存对话列表项（不含完整数据）"""
    id: int
    name: str
    character_desc: str
    style: Optional[str] = None
    dialogue_count: int
    created_at: str
    updated_at: str


# ============================================
# 对话生成模型
# ============================================


class DialogueGenerateRequest(BaseModel):
    """对话生成请求"""
    character_description: str
    num_dialogues: int = 10
    style: Optional[str] = None
    custom_prompt: Optional[str] = None
