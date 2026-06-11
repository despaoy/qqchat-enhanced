"""数据集存储管理工具
将现有数据集备份到data/datasets/目录，方便后续再次训练
"""

import json
import shutil
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


class DatasetManager:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).parent
        self.datasets_dir = self.base_dir / "data" / "datasets"
        self.index_path = self.datasets_dir / "index.json"
        self.datasets_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> Dict[str, Any]:
        if self.index_path.exists():
            with open(self.index_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"version": "1.0", "created_at": datetime.now().isoformat(), "datasets": {}}

    def _save_index(self, index: Dict[str, Any]):
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

    def _compute_hash(self, data: Any) -> str:
        return hashlib.md5(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def store_dataset(self, src_path: Path, description: str = "", fmt: str = "dialogues",
                      role: str = "", source: str = "", tags: List[str] = None) -> Dict[str, Any]:
        with open(src_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        content_hash = self._compute_hash(data)
        stem = src_path.stem
        dataset_dir = self.datasets_dir / stem
        dataset_dir.mkdir(exist_ok=True)

        dst = dataset_dir / src_path.name
        shutil.copy2(src_path, dst)

        info = {
            "description": description,
            "format": fmt,
            "role": role,
            "source": source,
            "tags": tags or [],
            "original_path": str(src_path),
            "stored_path": str(dst),
            "sample_count": len(data),
            "content_hash": content_hash,
            "stored_at": datetime.now().isoformat(),
        }

        with open(dataset_dir / "dataset_info.json", 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2, ensure_ascii=False)

        index = self._load_index()
        index["datasets"][src_path.name] = info
        self._save_index(index)

        print(f"已存储: {src_path.name} -> {dst} ({len(data)} 条)")
        return info

    def list_datasets(self) -> Dict[str, Any]:
        return self._load_index()

    def restore_dataset(self, filename: str, dst_dir: Optional[Path] = None) -> bool:
        index = self._load_index()
        if filename not in index["datasets"]:
            print(f"数据集不存在: {filename}")
            return False

        info = index["datasets"][filename]
        stored_path = Path(info["stored_path"])

        if not stored_path.exists():
            stem = Path(filename).stem
            stored_path = self.datasets_dir / stem / filename

        if not stored_path.exists():
            print(f"存储文件不存在: {stored_path}")
            return False

        target = dst_dir or self.base_dir / filename
        shutil.copy2(stored_path, target)
        print(f"已恢复: {stored_path} -> {target}")
        return True

    def init_default_datasets(self):
        default_datasets = {
            "hutao_dialogues.json": {
                "description": "胡桃对话数据集（原始格式，train_lora.py使用）",
                "format": "dialogues",
                "role": "hutao",
                "source": "原神角色对话",
                "tags": ["hutao", "dialogues", "training"],
            },
            "hutao_lora_dataset.json": {
                "description": "胡桃LoRA训练数据集（instruction格式，兼容旧版）",
                "format": "instruction",
                "role": "hutao",
                "source": "从hutao_dialogues.json转换",
                "tags": ["hutao", "lora", "instruction"],
            },
        }

        stored_count = 0
        for filename, meta in default_datasets.items():
            src = self.base_dir / filename
            if src.exists():
                self.store_dataset(
                    src_path=src,
                    description=meta["description"],
                    fmt=meta["format"],
                    role=meta["role"],
                    source=meta["source"],
                    tags=meta.get("tags", []),
                )
                stored_count += 1
            else:
                print(f"跳过（文件不存在）: {filename}")

        print(f"\n初始化完成: 共存储 {stored_count} 个数据集")
        print(f"存储位置: {self.datasets_dir}")
        print(f"索引文件: {self.index_path}")


def main():
    parser = argparse.ArgumentParser(description="数据集存储管理工具")
    parser.add_argument("command", choices=["init", "list", "restore"], help="操作命令")
    parser.add_argument("--file", type=str, help="恢复时指定文件名")
    parser.add_argument("--dest", type=str, help="恢复目标目录")
    args = parser.parse_args()

    manager = DatasetManager()

    if args.command == "init":
        manager.init_default_datasets()
    elif args.command == "list":
        index = manager.list_datasets()
        print(f"数据集索引 (版本 {index.get('version', 'unknown')}):")
        print(f"创建时间: {index.get('created_at', 'unknown')}")
        print()
        for name, info in index.get("datasets", {}).items():
            print(f"  {name}:")
            print(f"    描述: {info.get('description', '')}")
            print(f"    格式: {info.get('format', '')}")
            print(f"    样本数: {info.get('sample_count', 0)}")
            print(f"    存储路径: {info.get('stored_path', '')}")
            print()
    elif args.command == "restore":
        if not args.file:
            print("请指定 --file 参数")
            return
        dst = Path(args.dest) if args.dest else None
        manager.restore_dataset(args.file, dst)


if __name__ == "__main__":
    main()
