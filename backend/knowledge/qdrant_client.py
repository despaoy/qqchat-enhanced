"""
Qdrant 向量数据库客户端（阶段2.6 预留模块）

当前使用 Faiss 进行向量检索，Qdrant 作为后续升级选项。
Qdrant 优势：
- 内置 CRUD API（无需手动管理索引）
- 支持过滤搜索（按知识库ID、分类等）
- 支持分布式部署
- 持久化存储，无需重建索引

迁移路径：
1. docker run qdrant/qdrant
2. pip install qdrant-client
3. 重写 knowledge/vector_db.py 使用 Qdrant
4. 批量迁移现有向量到 Qdrant
"""
