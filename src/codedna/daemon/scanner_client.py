"""
Scanner client for invoking the Rust Fast Scanner.
Per ADR-002: Subprocess IPC model with stdin/stdout JSON protocol.
"""

import asyncio
import json
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class ScannerResult:
    score: Optional[float]
    partial_vector: Optional[List[float]]
    latency_ms: float
    error: Optional[str]
    degraded: bool = False


def get_rust_scanner_path() -> Optional[Path]:
    """Get the path to the Rust scanner binary.
    
    Searches in order:
    1. rust-scanner/target/release/codedna-scanner (after cargo build)
    2. bin/codedna-scanner (after manual install/copy)
    3. Installed alongside the Python package
    """
    # Start from package root
    package_dir = Path(__file__).parent.parent.parent
    
    scanner_paths = [
        # Primary: cargo build output
        package_dir / "rust-scanner" / "target" / "release" / "codedna-scanner",
        package_dir / "rust-scanner" / "target" / "release" / "codedna-scanner.exe",
        # Secondary: bin directory (for manual installation)
        package_dir / "bin" / "codedna-scanner",
        package_dir / "bin" / "codedna-scanner.exe",
        # Tertiary: check $PATH for system-installed scanner
        Path("/usr/local/bin/codedna-scanner"),
        Path.home() / ".local" / "bin" / "codedna-scanner",
    ]
    
    for path in scanner_paths:
        if path.exists():
            return path
    return None


async def invoke_scanner(
    scan_type: str,
    language: str,
    content: str,
    file_path: str = "",
    baseline_vector: Optional[List[float]] = None,
) -> ScannerResult:
    """
    Invoke the scanner with the given parameters.
    
    Per ADR-002: Scanner communicates over stdin/stdout JSON.
    Falls back to Python-based scoring if scanner unavailable.
    
    Args:
        scan_type: Type of scan (scan_file, scan_diff)
        language: Programming language
        content: Source code content
        file_path: Path to the file being scanned
        baseline_vector: Optional 32-dim baseline vector for comparison
    """
    start_time = time.time()
    scanner_path = get_rust_scanner_path()
    
    if scanner_path is None:
        # Use Python fallback - compute score from feature vector
        from codedna.harvester.features import extract_features
        vector = extract_features(content)
        target_list = vector.to_list()
        
        if baseline_vector:
            # Use baseline comparison
            similarity = compute_baseline_similarity(target_list, baseline_vector)
            score = round((0.5 + similarity * 0.5) * 100) / 100
        else:
            score = _estimate_score(target_list)
        
        return ScannerResult(
            score=score,
            partial_vector=target_list,
            latency_ms=(time.time() - start_time) * 1000,
            error=None,
            degraded=False,
        )
    
    try:
        request = {
            "type": scan_type,
            "language": language,
            "content": content,
            "fingerprint_id": "",
            "baseline_vector": baseline_vector,  # Pass baseline to Rust for comparison
            "file_path": file_path,
        }
        
        process = await asyncio.create_subprocess_exec(
            str(scanner_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        request_json = json.dumps(request) + "\n"
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=request_json.encode()),
            timeout=2.0,
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        if process.returncode != 0:
            logger.error(f"Scanner exited with code {process.returncode}: {stderr.decode()}")
            return ScannerResult(
                score=None,
                partial_vector=None,
                latency_ms=latency_ms,
                error=f"Scanner error: {stderr.decode()}",
                degraded=True,
            )
        
        response = json.loads(stdout.decode().strip())
        
        return ScannerResult(
            score=response.get("score"),
            partial_vector=response.get("partial_vector"),
            latency_ms=response.get("latency_ms", latency_ms),
            error=response.get("error"),
            degraded=response.get("error") is not None,
        )
        
    except asyncio.TimeoutError:
        logger.error("Scanner timed out after 2s")
        if process:
            process.kill()
        return ScannerResult(
            score=None,
            partial_vector=None,
            latency_ms=(time.time() - start_time) * 1000,
            error="Scanner timed out",
            degraded=True,
        )
    except Exception as e:
        logger.error(f"Scanner invocation failed: {e}")
        return ScannerResult(
            score=None,
            partial_vector=None,
            latency_ms=(time.time() - start_time) * 1000,
            error=str(e),
            degraded=True,
        )


def _estimate_score(vector: List[float]) -> float:
    """Estimate DNA score from feature vector."""
    if not vector:
        return 0.5
    
    # Use variance as a proxy for "typical" code
    mean = sum(vector) / len(vector)
    variance = sum((v - mean) ** 2 for v in vector) / len(vector)
    
    # Higher variance indicates more structured code
    score = 0.7 + min(variance * 2, 0.25)
    return round(score * 100) / 100


def compute_baseline_similarity(target_vector: List[float], baseline_vector: List[float]) -> float:
    """
    Compute cosine similarity between target and baseline feature vectors.
    
    Returns a score between 0.0 and 1.0 where:
    - 1.0 = perfect match (identical coding style)
    - 0.0 = completely different coding style
    - Values above 0.85 indicate likely same author
    """
    import math
    
    if not target_vector or not baseline_vector:
        return 0.5
    
    if len(target_vector) != len(baseline_vector):
        # Fall back to variance-based scoring if dimensions don't match
        return _estimate_score(target_vector)
    
    # Compute cosine similarity
    dot_product = sum(t * b for t, b in zip(target_vector, baseline_vector))
    target_magnitude = math.sqrt(sum(v * v for v in target_vector))
    baseline_magnitude = math.sqrt(sum(v * v for v in baseline_vector))
    
    if target_magnitude == 0 or baseline_magnitude == 0:
        return 0.5
    
    similarity = dot_product / (target_magnitude * baseline_magnitude)
    
    # Clamp to [0, 1] range (numerical precision can cause slight deviations)
    return max(0.0, min(1.0, similarity))


async def invoke_scanner_with_baseline(
    scan_type: str,
    language: str,
    content: str,
    file_path: str,
    baseline_vector: List[float],
) -> ScannerResult:
    """
    Invoke the scanner with a baseline fingerprint for comparison.
    
    Per design spec: Scans should compare against baseline fingerprint.
    Returns a DNA score based on cosine similarity to baseline.
    """
    from codedna.harvester.features import extract_features
    
    start_time = time.time()
    
    # Extract features from content
    vector = extract_features(content)
    target_list = vector.to_list()
    
    # Compute similarity against baseline
    similarity = compute_baseline_similarity(target_list, baseline_vector)
    
    # Scale similarity to DNA score (0.5-1.0 range)
    # Similarity of 0.5 = 0.5 DNA score, similarity of 1.0 = 1.0 DNA score
    dna_score = round((0.5 + similarity * 0.5) * 100) / 100
    
    return ScannerResult(
        score=dna_score,
        partial_vector=target_list,
        latency_ms=(time.time() - start_time) * 1000,
        error=None,
        degraded=False,
    )
