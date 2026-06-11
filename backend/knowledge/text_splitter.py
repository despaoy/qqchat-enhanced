"""
文本分块工具模块 - 项目统一文本分割策略
段落优先 → 句子分割 → 定长截断，三阶递进式中文语义感知分块
"""

from typing import List


def smart_text_split(text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
    """智能文本分块：段落优先 → 句子分割 → 定长截断

    Args:
        text: 输入文本
        chunk_size: 每个分块的最大字符数
        overlap: 分块间的重叠字符数

    Returns:
        文本分块列表
    """
    if not text:
        return []

    PAIRS = [('「', '」'), ('『', '』'), ('【', '】'), ('《', '》'), ('（', '）'), ('"', '"'), ("'", "'")]

    def _inside_pair(t: str, pos: int) -> bool:
        for left, right in PAIRS:
            lc = t[:pos].count(left)
            rc = t[:pos].count(right)
            if lc > rc:
                return True
        return False

    SENTENCE_ENDS = set('。！？；.!?;\n')

    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks = []
    current_chunk = []
    current_length = 0

    for para in paragraphs:
        para_length = len(para)
        if para_length > chunk_size:
            sentences = []
            sentence_start = 0
            for i, char in enumerate(para):
                if char in SENTENCE_ENDS and not _inside_pair(para, i):
                    s = para[sentence_start:i + 1].strip()
                    if s:
                        sentences.append(s)
                    sentence_start = i + 1
            if sentence_start < para_length and (s := para[sentence_start:].strip()):
                sentences.append(s)
            if not sentences:
                sentences = [para[i:i + chunk_size] for i in range(0, para_length, chunk_size)]

            for s in sentences:
                sl = len(s)
                if current_length + sl <= chunk_size:
                    current_chunk.append(s)
                    current_length += sl
                else:
                    if current_chunk:
                        chunks.append(' '.join(current_chunk))
                    if overlap > 0 and current_chunk:
                        tail = ' '.join(current_chunk[-2:]) if len(current_chunk) >= 2 else current_chunk[-1]
                        tail = tail[-overlap:] if len(tail) > overlap else tail
                        current_chunk = [tail, s]
                        current_length = len(tail) + sl
                    else:
                        current_chunk = [s]
                        current_length = sl
        else:
            if current_length + para_length <= chunk_size:
                current_chunk.append(para)
                current_length += para_length
            else:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                if overlap > 0 and current_chunk:
                    tail = ' '.join(current_chunk[-2:]) if len(current_chunk) >= 2 else current_chunk[-1]
                    tail = tail[-overlap:] if len(tail) > overlap else tail
                    current_chunk = [tail, para]
                    current_length = len(tail) + para_length
                else:
                    current_chunk = [para]
                    current_length = para_length

    if current_chunk:
        chunks.append(' '.join(current_chunk))
    return chunks


# 旧名兼容
simple_text_split = smart_text_split
