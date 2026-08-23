"""
scanner.py - 孤儿文件扫描器
支持并行扫描多个文件夹，找出 JPG 已删除但 RAW/PNG 残留的冗余文件
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from .utils import find_jpg_orphans, format_size


@dataclass
class ScanProgress:
    """扫描进度信息。"""
    folders_total: int = 0
    folders_completed: int = 0
    current_folder: str = ""
    files_scanned: int = 0
    orphans_found: int = 0


@dataclass
class ScanResult:
    """单个文件夹的扫描结果。"""
    folder: str
    success: bool
    error: Optional[str] = None
    orphans: List[dict] = field(default_factory=list)
    total_size_bytes: int = 0
    duration_sec: float = 0.0

    @property
    def total_size_formatted(self) -> str:
        return format_size(self.total_size_bytes)

    @property
    def orphan_count(self) -> int:
        return len(self.orphans)


def scan_single_folder(folder: str) -> ScanResult:
    """
    扫描单个文件夹。
    
    Args:
        folder: 文件夹路径
        
    Returns:
        ScanResult 对象
    """
    start = time.time()
    if not os.path.isdir(folder):
        return ScanResult(
            folder=folder, success=False,
            error=f"文件夹不存在: {folder}"
        )

    try:
        orphans = find_jpg_orphans(folder)
        total_size = sum(o["size_bytes"] for o in orphans)
        duration = time.time() - start

        return ScanResult(
            folder=folder,
            success=True,
            orphans=orphans,
            total_size_bytes=total_size,
            duration_sec=duration,
        )
    except Exception as e:
        return ScanResult(
            folder=folder, success=False,
            error=str(e)
        )


def scan_folders_parallel(
    folders: List[str],
    max_workers: int = 4,
    progress_callback: Optional[Callable[[ScanProgress], None]] = None,
) -> List[ScanResult]:
    """
    并行扫描多个文件夹。
    
    Args:
        folders: 文件夹路径列表
        max_workers: 最大并行数（默认为 4）
        progress_callback: 进度回调函数
        
    Returns:
        ScanResult 列表
    """
    results = []
    progress = ScanProgress(folders_total=len(folders))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_folder = {
            executor.submit(scan_single_folder, f): f
            for f in folders
        }

        for future in as_completed(future_to_folder):
            folder = future_to_folder[future]
            progress.current_folder = folder

            try:
                result = future.result()
                results.append(result)
                progress.orphans_found += result.orphan_count
            except Exception as e:
                results.append(ScanResult(
                    folder=folder, success=False, error=str(e)
                ))

            progress.folders_completed += 1

            if progress_callback:
                progress_callback(progress)

    return results


def delete_orphans(orphans: List[dict]) -> tuple:
    """
    批量将孤儿文件移入回收站。
    
    Args:
        orphans: 孤儿文件列表（来自 ScanResult.orphans）
        
    Returns:
        (成功数, 失败数, 失败文件列表)
    """
    from .utils import send_to_trash

    success = 0
    failed = 0
    failed_files = []

    for item in orphans:
        try:
            if send_to_trash(item["path"]):
                success += 1
            else:
                failed += 1
                failed_files.append(item["path"])
        except Exception:
            failed += 1
            failed_files.append(item["path"])

    return success, failed, failed_files
