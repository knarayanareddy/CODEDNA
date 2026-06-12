"""CodeDNA Harvester - Orchestrates feature extraction from repositories."""
import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from codedna.harvester.language_adapter import get_adapter, HarvesterConfig

logger = logging.getLogger(__name__)

class Harvester:
    def __init__(self, repo_path: str, config: Optional[HarvesterConfig] = None):
        self.repo_path = Path(repo_path)
        self.config = config or HarvesterConfig()
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")
        self.adapter = get_adapter(self.config.language)
        if not self.adapter:
            raise ValueError(f"Unsupported language: {self.config.language}")

    async def build_baseline(self, progress_callback: Optional[Callable[[float], None]] = None) -> Dict[str, Any]:
        import time
        start_time = time.time()
        logger.info(f"Starting baseline build for: {self.repo_path}")
        
        async def call_progress(p: float):
            if progress_callback:
                res = progress_callback(p)
                if asyncio.iscoroutine(res):
                    await res
        
        git_info = await self._get_git_info()
        files = self._discover_files()
        logger.info(f"Found {len(files)} source files to process")
        await call_progress(0.1)
        all_vectors = []
        processed_files = 0
        for file_path in files:
            try:
                features = await self._process_file(file_path)
                if features:
                    all_vectors.extend(features)
                processed_files += 1
                if files:
                    progress = 0.1 + (0.8 * processed_files / len(files))
                    await call_progress(progress)
            except Exception as e:
                logger.warning(f"Failed to process {file_path}: {e}")
                continue
        fingerprint = self._compute_fingerprint(all_vectors)
        duration = time.time() - start_time
        logger.info(f"Baseline build completed in {duration:.2f}s")
        await call_progress(1.0)
        return {"model": fingerprint, "vector_dims": 32, "commit_hash": git_info.get("commit_hash", ""),
                "commit_count": git_info.get("commit_count", 0), "file_count": processed_files,
                "duration_s": duration, "feature_count": len(all_vectors)}

    async def _get_git_info(self) -> Dict[str, Any]:
        try:
            result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo_path, capture_output=True, text=True, timeout=10)
            commit_hash = result.stdout.strip() if result.returncode == 0 else ""
            result = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=self.repo_path, capture_output=True, text=True, timeout=10)
            commit_count = int(result.stdout.strip()) if result.returncode == 0 else 0
            return {"commit_hash": commit_hash, "commit_count": commit_count}
        except Exception as e:
            logger.warning(f"Failed to get git info: {e}")
            return {"commit_hash": "", "commit_count": 0}

    def _discover_files(self) -> list:
        files = []
        extensions = getattr(self.adapter, 'extensions', ['.py'])
        for root, dirs, filenames in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if not self._should_skip_dir(d)]
            for filename in filenames:
                if any(filename.endswith(ext) for ext in extensions):
                    files.append(Path(root) / filename)
        return files

    def _should_skip_dir(self, dirname: str) -> bool:
        skip_dirs = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", "env", ".env", "dist", "build", ".eggs"}
        return dirname in skip_dirs or dirname.startswith(".")

    async def _process_file(self, file_path: Path) -> list:
        try:
            file_size = file_path.stat().st_size
            if file_size > self.config.max_file_bytes:
                return []
        except OSError:
            return []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return []
        try:
            return [self.adapter.extract_features(content, self.config)]
        except Exception:
            return []

    def _compute_fingerprint(self, vectors: list) -> bytes:
        import struct
        import numpy as np
        if not vectors:
            return struct.pack(f"{32}f", *[0.0] * 32)
        vectors_array = np.array([v.to_list() for v in vectors])
        mean_vector = np.mean(vectors_array, axis=0)
        std_vector = np.std(vectors_array, axis=0)
        combined = np.concatenate([mean_vector, std_vector])
        return combined.astype(np.float32).tobytes()
