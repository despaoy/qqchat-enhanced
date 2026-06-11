#!/usr/bin/env python3
"""
批量导入原神知识库到向量数据库
改进版：支持智能分块、元数据提取、进度显示和去重
"""

import sys
import argparse
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 尝试导入tqdm用于进度条
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    logger.info("未找到tqdm库，将使用简单进度日志")

from .text_splitter import smart_text_split
from .vector_db import get_vector_db


def extract_metadata(file_path: Path, content: str) -> Dict[str, Any]:
    """
    从文件路径和内容中提取元数据
    
    Args:
        file_path: 文件路径
        content: 文件内容
    
    Returns:
        元数据字典
    """
    # 从路径提取类别（父目录名），映射为中文分类
    dir_name = file_path.parent.name if file_path.parent.name else "unknown"
    category_map = {
        "characters": "角色",
        "events": "事件",
        "world": "世界",
    }
    category = category_map.get(dir_name, dir_name)
    
    # 尝试从内容提取标题（第一行）
    title = file_path.stem  # 默认使用文件名
    lines = content.strip().split('\n')
    
    # 计算基本统计
    lines = content.split('\n')
    non_empty_lines = [line for line in lines if line.strip()]
    
    return {
        "category": category,
        "source_file": str(file_path),
        "filename": title,
        "file_size_chars": len(content),
        "file_size_lines": len(lines),
        "non_empty_lines": len(non_empty_lines),
    }


def generate_chunk_id(file_path: str, chunk_index: int, chunk_content: str) -> str:
    """
    生成分块唯一ID
    
    Args:
        file_path: 文件路径
        chunk_index: 分块索引
        chunk_content: 分块内容
    
    Returns:
        唯一ID字符串
    """
    # 使用文件路径、分块索引和内容哈希生成ID
    hash_input = f"{file_path}_{chunk_index}_{chunk_content}"
    return hashlib.md5(hash_input.encode('utf-8')).hexdigest()


def import_genshin_knowledge(
    knowledge_base_path: str,
    chunk_size: int = 600,
    overlap: int = 150,
    skip_existing: bool = True,
    use_progress_bar: bool = True
):
    """
    导入原神知识库
    
    Args:
        knowledge_base_path: 知识库目录路径
        chunk_size: 分块大小（字符数）
        overlap: 分块重叠字符数
        skip_existing: 是否跳过已存在的文档（基于文件路径检测）
        use_progress_bar: 是否使用进度条
    """
    knowledge_base_dir = Path(knowledge_base_path)
    
    if not knowledge_base_dir.exists():
        logger.error(f"知识库目录不存在: {knowledge_base_dir}")
        return
    
    if not knowledge_base_dir.is_dir():
        logger.error(f"知识库路径不是目录: {knowledge_base_dir}")
        return
    
    vector_db = get_vector_db()
    
    # 获取所有txt文件
    txt_files = list(knowledge_base_dir.rglob("*.txt"))
    if not txt_files:
        logger.warning(f"在 {knowledge_base_dir} 中未找到.txt文件")
        return
    
    logger.info(f"找到 {len(txt_files)} 个文本文件")
    
    # 准备进度迭代器
    if use_progress_bar and HAS_TQDM:
        file_iter = tqdm(txt_files, desc="处理文件", unit="file")
    else:
        file_iter = txt_files
        logger.info("开始处理文件...")
    
    total_docs = 0
    total_chunks = 0
    skipped_files = 0
    
    for txt_file in file_iter:
        try:
            # 检查是否已处理（基于文件路径）
            if skip_existing:
                # 检查文件是否已处理
                source_file = str(txt_file)
                existing_source_files = {meta.get("source_file") for meta in vector_db.metadata}
                if source_file in existing_source_files:
                    logger.info(f"文件已存在，跳过: {txt_file}")
                    skipped_files += 1
                    continue
            
            # 读取文件内容
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                logger.warning(f"文件内容为空: {txt_file}")
                continue
            
            # 提取元数据
            metadata = extract_metadata(txt_file, content)
            title = txt_file.stem
            
            # 智能分块
            chunks = smart_text_split(content, chunk_size=chunk_size, overlap=overlap)
            
            if not chunks:
                logger.warning(f"文件未产生分块: {txt_file}")
                continue
            
            # 准备向量数据库文档
            vector_docs = []
            for i, chunk_content in enumerate(chunks):
                chunk_id = generate_chunk_id(str(txt_file), i, chunk_content)
                
                # 增强标题：包含类别信息，提高检索精度
                enhanced_title = f"{title} ({metadata.get('category', 'unknown')})"
                
                vector_docs.append({
                    "id": chunk_id,  # 唯一ID
                    "chunk_index": i,
                    "chunk_id": chunk_id,  # 兼容原有字段
                    "title": enhanced_title,
                    "original_title": title,  # 保留原始标题
                    "content": chunk_content,
                    "source_type": "text",
                    **metadata  # 合并元数据
                })
            
            # 添加到向量数据库
            if vector_docs:
                vector_db.add_documents(vector_docs)
                total_chunks += len(vector_docs)
                logger.debug(f"文件 {txt_file.name}: 向量化 {len(vector_docs)} 个片段")
            
            total_docs += 1
            
        except Exception as e:
            logger.error(f"处理文件失败 {txt_file}: {e}")
            logger.error(f"异常详情: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    # 显示统计
    stats = vector_db.get_stats()
    logger.info(f"向量数据库统计: {stats}")
    logger.info(f"成功导入 {total_docs} 个文档，共 {total_chunks} 个片段")
    if skipped_files > 0:
        logger.info(f"跳过 {skipped_files} 个已存在的文件")
    
    return total_docs, total_chunks


def main():
    """主函数：解析命令行参数并执行导入"""
    parser = argparse.ArgumentParser(description="导入原神知识库到向量数据库")
    parser.add_argument(
        "--knowledge-base",
        type=str,
        default=None,
        help="知识库目录路径（默认：项目根目录下的genshin_knowledge_base）"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=600,
        help="分块大小（字符数，默认：600）"
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=150,
        help="分块重叠字符数（默认：150）"
    )
    parser.add_argument(
        "--no-skip",
        action="store_false",
        dest="skip_existing",
        default=True,
        help="不跳过已存在的文档（默认跳过）"
    )
    parser.add_argument(
        "--no-progress",
        action="store_false",
        dest="use_progress_bar",
        default=True,
        help="禁用进度条"
    )
    
    args = parser.parse_args()
    
    if args.knowledge_base is None:
        args.knowledge_base = str(Path(__file__).parent.parent / "genshin_knowledge_base")
    
    logger.info(f"开始导入知识库: {args.knowledge_base}")
    logger.info(f"分块大小: {args.chunk_size}, 重叠: {args.overlap}")
    
    import_genshin_knowledge(
        knowledge_base_path=args.knowledge_base,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        skip_existing=args.skip_existing,
        use_progress_bar=args.use_progress_bar
    )


if __name__ == "__main__":
    main()