🧬 CODEDNA
Comprehensive Engineering Design Document

Version 1.0 | Fully Local Git-Native Style Intelligence Engine & Code Immune System
TABLE OF CONTENTS

    Project Overview & Vision
    Goals, Non-Goals & Constraints
    System Architecture
    Module Breakdown
        4.1 Git Corpus Harvester
        4.2 AST Feature Extractor
        4.3 Feature Vector Builder
        4.4 StyleDNA Fingerprint Engine
        4.5 Immune System Scanner (Rust)
        4.6 Scorer & Localizer
        4.7 Explainer Engine
        4.8 Evolution Tracker
        4.9 Integration Layer (IDE / Git Hooks / CLI)
        4.10 Local API Server
        4.11 Dashboard & Visualization UI
    Data Models & Schemas
    API Specifications
    Directory Structure
    Configuration System
    Feature Engineering Deep Dive
    Fingerprint Modeling Deep Dive
    Scoring & Anomaly Detection Deep Dive
    Evolution & Style Drift Deep Dive
    Multi-Language Support
    Privacy & Security Model
    Storage & Persistence
    Logging, Observability & Debugging
    Testing Strategy
    Build, Packaging & Installation
    Platform Support Matrix
    Performance Targets & Benchmarks
    Error Handling Strategy
    Dependency Registry
    Milestone & Phased Rollout Plan
    Open Questions & Future Work

1. Project Overview & Vision
1.1 What is CodeDNA?

CodeDNA is a fully local, zero-cloud developer tool that learns your personal coding "voice" from your own git history, builds a deep stylometric fingerprint of how you write code, and then acts as a style immune system — flagging, explaining, and optionally blocking code that doesn't match your established patterns.

It operates at three granularities:

    Function level — Does this function feel like yours?
    File level — Does this entire file match your style distribution?
    PR / diff level — Does this changeset match the developer it claims to be from?

It is not a linter. It is not a formatter. It does not enforce rules you write. It learns the implicit, consistent patterns in your code — naming habits, control-flow preferences, abstraction tendencies, error-handling style, comment density and phrasing — and uses them to detect when "foreign" code has entered your codebase, whether that code comes from an AI assistant, a copy-paste from Stack Overflow, a teammate's PR, or simply your own past self in a very different mindset.

Everything runs on your machine. Nothing leaves it.
1.2 The Problem Being Solved

Modern software development has a growing but under-articulated problem: code provenance opacity.

    AI code generation tools (Copilot, Claude, ChatGPT) produce code that is stylistically inconsistent with the surrounding codebase — yet it merges silently.
    Copy-pasted snippets from external sources carry patterns, idioms, and habits foreign to your own.
    Large PRs from collaborators can contain sections that simply don't fit the established voice of the file they're modifying.
    Your own style evolves over months and years, but no tool tells you when or how — or alerts you when a commit looks more like "2019 you" than "2024 you."

The result is style entropy: codebases that accumulate multiple, inconsistent voices over time, making them harder to read, maintain, and reason about.

CodeDNA treats this as a first-class engineering problem. Your commit history is a rich, labeled dataset of your code. CodeDNA mines it, models it, and turns it into a living fingerprint — a StyleDNA — that acts as a reference point for everything that follows.
1.3 Design Philosophy
Principle	Description
Local-first	All processing, storage, and inference on the user's machine. No telemetry, no cloud.
History-native	Git is the source of truth. Your commits are the training data.
Explainable	Every flag includes a feature-delta explanation anchored in your own baseline. No black boxes.
Non-blocking by default	Warn first; block only if the user opts in. Alerts must earn trust before enforcement.
Language-aware	Features are extracted per-language. Python habits are not Python-shaped Go habits.
Multi-voice aware	You have a test style, a prod style, a scripting style. The system learns all of them.
Incrementally correct	The fingerprint updates as you write more code. Your style's drift is modeled, not erased.
Composable	CLI, IDE extension, git hook, and API are all first-class interfaces.
2. Goals, Non-Goals & Constraints
2.1 Goals (In Scope)

    Mine personal git history to build a labeled corpus of the user's own code
    Extract deep AST-based stylometric feature vectors per function, file, and commit
    Build a "StyleDNA" baseline model representing the user's coding style distribution
    Cluster style into multiple "voices" (UMAP + HDBSCAN) with a visualization timeline
    Score incoming code (functions, files, diffs) against the baseline
    Localize "foreign" regions within a file at function granularity
    Explain every flag in plain language using feature deltas vs. the user's own baseline
    Detect and report style evolution over time (era detection, shift detection)
    Provide a pre-commit git hook for blocking / warning at commit time
    Provide a VS Code extension and Vim plugin that surface scores inline
    Provide a CLI for ad-hoc scoring and batch analysis
    Persist all data in local SQLite; export to JSON/CSV
    Support Python, Go, JavaScript, TypeScript, Rust, and Java at launch
    Run incrementally: only re-extract changed files on subsequent runs

2.2 Non-Goals (Explicitly Out of Scope)

    ❌ Enforcing formatting or linting rules (that's what formatters do)
    ❌ Cloud sync, telemetry, or any remote model inference
    ❌ Authorship deanonymization of other people's code (this is a privacy threat; see §14)
    ❌ Plagiarism detection in the academic sense
    ❌ Blocking autonomous AI code generation (CodeDNA runs after code is written)
    ❌ Integration with code review platforms (GitHub, GitLab) in v1.0
    ❌ Team-wide shared fingerprints (each user has their own; team features are future work)
    ❌ Training or fine-tuning any remote LLM on your code

2.3 Constraints

    Must work fully offline: zero network required after initial dependency installation
    All model inference uses classical ML or local embeddings (no Ollama/cloud required)
    Incremental scan latency must be < 500ms for IDE integration on files up to 2,000 lines
    Full corpus rebuild from a 5-year git history must complete in < 10 minutes on modern hardware
    Must not require root/admin privileges
    Must handle repositories with millions of lines of code
    SQLite is the only required runtime dependency beyond the binary
    Pre-commit hook must add < 2s to commit time (fast-path scanner)

3. System Architecture
3.1 High-Level Architecture Diagram

text

┌─────────────────────────────────────────────────────────────────────────┐
│                            DEVELOPER'S MACHINE                          │
│                                                                         │
│  ┌─────────────┐    ┌────────────────────────────────────────────────┐  │
│  │             │    │              CODEDNA CORE                      │  │
│  │  Git Repo   │───►│                                                │  │
│  │  (History)  │    │  ┌──────────────┐    ┌──────────────────────┐ │  │
│  └─────────────┘    │  │ Git Corpus   │    │  AST Feature         │ │  │
│                     │  │ Harvester    │───►│  Extractor           │ │  │
│  ┌─────────────┐    │  │ (Python)     │    │  (tree-sitter)       │ │  │
│  │  IDE        │◄──►│  └──────────────┘    └──────────┬───────────┘ │  │
│  │  Extension  │    │                                 │             │  │
│  │  (VS Code / │    │  ┌──────────────────────────────▼───────────┐ │  │
│  │   Vim)      │    │  │         Feature Vector Builder           │ │  │
│  └─────────────┘    │  │         (Python / NumPy)                 │ │  │
│                     │  └──────────────────────┬────────────────────┘ │  │
│  ┌─────────────┐    │                         │                      │  │
│  │  CLI        │◄──►│  ┌──────────────────────▼────────────────────┐│  │
│  │  (codedna)  │    │  │         StyleDNA Fingerprint Engine       ││  │
│  └─────────────┘    │  │  ┌───────────┐  ┌──────────┐  ┌────────┐ ││  │
│                     │  │  │ Builder   │  │Clusterer │  │Evolver │ ││  │
│  ┌─────────────┐    │  │  │(baseline) │  │(UMAP+    │  │(drift) │ ││  │
│  │  Git Hook   │◄──►│  │  │           │  │HDBSCAN)  │  │        │ ││  │
│  │ (pre-commit)│    │  │  └───────────┘  └──────────┘  └────────┘ ││  │
│  └─────────────┘    │  └──────────────────────┬────────────────────┘│  │
│                     │                         │                      │  │
│  ┌─────────────┐    │  ┌──────────────────────▼────────────────────┐│  │
│  │  Dashboard  │◄──►│  │           IMMUNE SYSTEM                   ││  │
│  │  (Web UI)   │    │  │  ┌────────────┐ ┌─────────┐ ┌──────────┐ ││  │
│  │  Port 7432  │    │  │  │ Scanner.rs │ │ Scorer  │ │Explainer │ ││  │
│  └─────────────┘    │  │  │  (fast)    │ │ (Python)│ │ (Python) │ ││  │
│                     │  │  └────────────┘ └─────────┘ └──────────┘ ││  │
│                     │  └──────────────────────┬────────────────────┘│  │
│                     │                         │                      │  │
│                     │  ┌──────────────────────▼────────────────────┐│  │
│                     │  │    SQLite DB  +  FastAPI Local Server      ││  │
│                     │  │    (~/.codedna/codedna.db)                 ││  │
│                     │  └────────────────────────────────────────────┘│  │
│                     └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

3.2 Data Flow: Initial Fingerprint Build

text

Step 1:  User runs `codedna init` in a repository
Step 2:  Git Corpus Harvester walks the git log, filtering to the user's
         commits by author identity (email + name aliases)
Step 3:  Exclude: merges, bulk reformats, vendored files, generated code,
         lockfiles, large binary blobs
Step 4:  For each qualifying commit, extract the set of changed functions
         (using tree-sitter AST diff)
Step 5:  Feature Extractor builds a ~200-dimension StyleFeatures vector
         per function
Step 6:  Feature Vector Builder normalizes and stores vectors in SQLite
Step 7:  Fingerprint Builder computes per-language baseline distributions
         (mean, covariance, robust estimates)
Step 8:  Clusterer runs UMAP dimensionality reduction → HDBSCAN clustering
         to discover multiple style modes ("voices")
Step 9:  Evolver time-buckets the vectors and computes drift metrics
Step 10: Dashboard becomes available at http://localhost:7432
         showing style map, timeline, and top features

3.3 Data Flow: Real-Time Immune Scan

text

Step 1:  Trigger received: pre-commit hook / IDE save / CLI scan / API call
Step 2:  Scanner.rs identifies changed or new functions (fast path,
         tree-sitter incremental parse)
Step 3:  Feature Extractor runs on each changed function
Step 4:  Scorer computes:
           - overall_match_pct (0–100)
           - per-function scores
           - confidence_level
Step 5:  Detector localizes suspicious spans within each flagged function
Step 6:  Explainer generates plain-language feature-delta explanation
         anchored in the user's own baseline statistics
Step 7:  Verdict emitted:
           - MATCH (>= threshold): pass silently
           - WARN (below warn_threshold): print warning, allow commit
           - BLOCK (below block_threshold, opt-in): block commit, show report
Step 8:  Result stored in SQLite (scan_results table)
Step 9:  Dashboard updated via SSE

3.4 Component Ownership
Component	Language	Owns
Git Corpus Harvester	Python (GitPython)	Commit traversal, author filtering, sample extraction
AST Feature Extractor	Python (tree-sitter)	Multi-language AST parsing, feature counting
Feature Vector Builder	Python (NumPy/Pandas)	Vector assembly, normalization, storage
StyleDNA Fingerprint Engine	Python (scikit-learn, UMAP, HDBSCAN)	Baseline modeling, clustering, drift
Immune System Scanner	Rust	Fast file traversal, incremental parse, change detection
Scorer & Localizer	Python	Distance scoring, suspicious span localization
Explainer	Python	Feature-delta explanation generation
Evolution Tracker	Python	Time-bucketing, drift metrics, era detection
Local API Server	Python (FastAPI)	REST + SSE, integration bridge
Dashboard UI	React + TypeScript	Visualization, configuration, reports
CLI	Python (Typer)	All user-facing commands
SQLite DB	SQLite (via SQLAlchemy)	All persistence
4. Module Breakdown
4.1 Git Corpus Harvester

Purpose: Walk the user's git history and produce a clean, labeled dataset of code samples authored by the user, suitable for feature extraction.

Key Engineering Requirements:

    Identity resolution: map multiple author emails and name variants to a single identity
    Sampling strategy: prefer commits in the "steady state" (exclude initial scaffolding, mass imports, bulk reformats)
    Contamination filtering: exclude vendored paths, generated files, lockfiles, minified code, and binary files
    Diff-aware extraction: extract only the added or modified function bodies per commit, not entire files

Python

# analyzer/git_parser.py

from dataclasses import dataclass, field
from typing import Iterator, List, Optional
from datetime import datetime
import git


@dataclass
class CodeSample:
    repo_path: str
    commit_sha: str
    author_email: str
    timestamp: datetime
    file_path: str
    language: str
    function_name: str
    function_body: str
    start_line: int
    end_line: int
    is_new: bool          # True = new function, False = modified
    commit_message: str


@dataclass
class HarvesterConfig:
    author_emails: List[str]       # Identity resolution
    author_names: List[str]        # Aliases
    exclude_paths: List[str] = field(default_factory=lambda: [
        "vendor/", "node_modules/", ".gen.", "_generated.",
        "*.min.js", "*.pb.go", "*.lock", "migrations/",
        "testdata/", "__pycache__/",
    ])
    min_function_lines: int = 3    # Ignore trivial stubs
    max_function_lines: int = 500  # Ignore massive legacy blobs
    min_commits: int = 50          # Minimum qualifying commits to build baseline
    exclude_bulk_reformats: bool = True
    bulk_reformat_threshold: int = 20  # > N files changed = likely reformat commit


class GitCorpusHarvester:
    def __init__(self, repo_path: str, config: HarvesterConfig):
        self.repo = git.Repo(repo_path)
        self.config = config
        self.extractor = ASTExtractor()

    def harvest(self) -> Iterator[CodeSample]:
        for commit in self._qualifying_commits():
            yield from self._extract_functions_from_commit(commit)

    def _qualifying_commits(self):
        for commit in self.repo.iter_commits():
            if not self._is_authored_by_user(commit):
                continue
            if self._is_merge_commit(commit):
                continue
            if self._is_bulk_reformat(commit):
                continue
            yield commit

    def _is_authored_by_user(self, commit) -> bool:
        email = commit.author.email.lower()
        name = commit.author.name.lower()
        return (
            any(e.lower() == email for e in self.config.author_emails) or
            any(n.lower() in name for n in self.config.author_names)
        )

    def _is_bulk_reformat(self, commit) -> bool:
        if not self.config.exclude_bulk_reformats:
            return False
        changed = list(commit.stats.files.keys())
        return len(changed) > self.config.bulk_reformat_threshold

    def _extract_functions_from_commit(self, commit) -> Iterator[CodeSample]:
        parent = commit.parents[0] if commit.parents else None
        for diff in commit.diff(parent):
            if self._should_skip_file(diff.b_path):
                continue
            lang = detect_language(diff.b_path)
            if lang is None:
                continue
            if diff.b_blob is None:
                continue
            source = diff.b_blob.data_stream.read().decode("utf-8", errors="replace")
            functions = self.extractor.extract_functions(source, lang)
            for fn in functions:
                if not (self.config.min_function_lines
                        <= fn.line_count
                        <= self.config.max_function_lines):
                    continue
                yield CodeSample(
                    repo_path=str(self.repo.working_dir),
                    commit_sha=commit.hexsha,
                    author_email=commit.author.email,
                    timestamp=datetime.fromtimestamp(commit.authored_date),
                    file_path=diff.b_path,
                    language=lang,
                    function_name=fn.name,
                    function_body=fn.body,
                    start_line=fn.start_line,
                    end_line=fn.end_line,
                    is_new=diff.new_file,
                    commit_message=commit.message.strip(),
                )

    def _should_skip_file(self, path: str) -> bool:
        if path is None:
            return True
        for pattern in self.config.exclude_paths:
            if pattern.replace("*", "") in path:
                return True
        return False

4.2 AST Feature Extractor

Purpose: Parse source code for any supported language using tree-sitter and extract structural features — not surface formatting, but deep patterns in how code is organized, named, and composed.

Why tree-sitter: It supports incremental parsing (critical for IDE latency), is robust to partial/broken code, handles 40+ languages from a single C library, and is already the parser inside VS Code and Neovim.

Python

# analyzer/ast_extractor.py

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import tree_sitter_python as tspython
import tree_sitter_go as tsgo
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
import tree_sitter_rust as tsrust
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser


LANGUAGE_REGISTRY: Dict[str, Any] = {
    "python":     Language(tspython.language()),
    "go":         Language(tsgo.language()),
    "javascript": Language(tsjavascript.language()),
    "typescript": Language(tstypescript.language_typescript()),
    "rust":       Language(tsrust.language()),
    "java":       Language(tsjava.language()),
}


@dataclass
class FunctionNode:
    name: str
    body: str
    start_line: int
    end_line: int
    line_count: int
    params: List[str]
    return_type: Optional[str]
    is_method: bool
    decorators: List[str]


@dataclass
class ASTFeatures:
    """Raw AST-derived counts and measurements for a single function."""

    # Identity
    function_name: str
    language: str

    # Naming
    name_length: int
    name_is_snake_case: bool
    name_is_camel_case: bool
    name_has_abbreviation: bool
    param_names: List[str]
    param_name_avg_length: float

    # Structure
    line_count: int
    param_count: int
    return_statement_count: int
    early_return_count: int       # returns not at the final line
    max_nesting_depth: int
    avg_nesting_depth: float
    blank_line_ratio: float

    # Control flow
    if_count: int
    else_count: int
    elif_count: int
    ternary_count: int
    for_count: int
    while_count: int
    comprehension_count: int
    match_case_count: int         # Python 3.10+ / Rust match

    # Abstractions
    lambda_count: int
    closure_count: int
    class_instantiation_count: int
    function_call_count: int
    chained_call_depth: int       # a.b().c().d() = depth 3

    # Error handling
    try_count: int
    except_count: int
    finally_count: int
    raise_count: int
    assert_count: int
    result_type_used: bool        # Rust Result<T>, Go (val, err) pattern

    # Mutability / state
    assignment_count: int
    augmented_assignment_count: int   # +=, -=, etc.
    global_var_references: int
    local_var_count: int

    # Comments & docs
    comment_count: int
    comment_line_ratio: float
    has_docstring: bool
    docstring_length: int
    inline_comment_count: int

    # Imports (file-level, normalized per function)
    import_count: int
    stdlib_import_ratio: float
    third_party_libs: List[str]   # Hashed/normalized names


class ASTExtractor:
    def __init__(self):
        self.parsers: Dict[str, Parser] = {}
        for lang, language_obj in LANGUAGE_REGISTRY.items():
            p = Parser(language_obj)
            self.parsers[lang] = p

    def extract_functions(self, source: str, language: str) -> List[FunctionNode]:
        parser = self.parsers.get(language)
        if parser is None:
            return []
        tree = parser.parse(bytes(source, "utf-8"))
        extractor = self._get_language_extractor(language)
        return extractor.extract_functions(tree, source)

    def extract_features(self, fn: FunctionNode, language: str) -> ASTFeatures:
        extractor = self._get_language_extractor(language)
        return extractor.extract_features(fn)

    def _get_language_extractor(self, language: str):
        from analyzer.supported_langs import (
            python_features, go_features, js_features,
            ts_features, rust_features, java_features,
        )
        mapping = {
            "python": python_features.PythonExtractor(),
            "go": go_features.GoExtractor(),
            "javascript": js_features.JSExtractor(),
            "typescript": ts_features.TSExtractor(),
            "rust": rust_features.RustExtractor(),
            "java": java_features.JavaExtractor(),
        }
        return mapping[language]

4.3 Feature Vector Builder

Purpose: Transform raw ASTFeatures into a normalized, numeric feature vector suitable for statistical modeling. Handle missing values, scaling, and encoding consistently.

Python

# analyzer/feature_builder.py

import numpy as np
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from sklearn.preprocessing import RobustScaler
import hashlib


@dataclass
class StyleVector:
    """
    Final numeric representation of a code sample.
    ~200 dimensions. All values are float32 after normalization.
    """
    # Raw features before normalization (for explainability)
    raw: Dict[str, float]
    # Normalized vector for modeling
    vector: np.ndarray
    # Metadata
    function_name: str
    file_path: str
    language: str
    commit_sha: str
    timestamp_epoch: int
    cluster_id: Optional[int] = None


class FeatureVectorBuilder:
    """
    Converts ASTFeatures → StyleVector.
    Maintains a fitted RobustScaler per language for normalization.
    """

    # Ordered list of scalar feature names extracted from ASTFeatures
    SCALAR_FEATURES = [
        "name_length", "name_is_snake_case", "name_is_camel_case",
        "name_has_abbreviation", "param_name_avg_length",
        "line_count", "param_count", "return_statement_count",
        "early_return_count", "max_nesting_depth", "avg_nesting_depth",
        "blank_line_ratio", "if_count", "else_count", "elif_count",
        "ternary_count", "for_count", "while_count", "comprehension_count",
        "match_case_count", "lambda_count", "closure_count",
        "class_instantiation_count", "function_call_count",
        "chained_call_depth", "try_count", "except_count", "finally_count",
        "raise_count", "assert_count", "result_type_used",
        "assignment_count", "augmented_assignment_count",
        "global_var_references", "local_var_count",
        "comment_count", "comment_line_ratio", "has_docstring",
        "docstring_length", "inline_comment_count",
        "import_count", "stdlib_import_ratio",
    ]

    # Derived ratio features (computed from scalar features)
    DERIVED_FEATURES = [
        "early_return_ratio",       # early_returns / return_statement_count
        "exception_to_try_ratio",   # except_count / max(try_count, 1)
        "comment_to_code_ratio",    # comment_count / line_count
        "control_flow_density",     # (if+for+while) / line_count
        "abstraction_density",      # (lambda+closure) / line_count
        "mutation_ratio",           # augmented_assignments / assignments
        "call_to_line_ratio",       # function_call_count / line_count
    ]

    def build(self, features: "ASTFeatures", sample: "CodeSample") -> StyleVector:
        raw = self._extract_scalars(features)
        raw.update(self._compute_derived(raw))
        lib_vector = self._encode_libraries(features.third_party_libs)
        raw_array = np.array([raw[k] for k in self.SCALAR_FEATURES + self.DERIVED_FEATURES],
                             dtype=np.float32)
        full_vector = np.concatenate([raw_array, lib_vector])
        return StyleVector(
            raw=raw,
            vector=full_vector,
            function_name=features.function_name,
            file_path=sample.file_path,
            language=sample.language,
            commit_sha=sample.commit_sha,
            timestamp_epoch=int(sample.timestamp.timestamp()),
        )

    def _extract_scalars(self, features: "ASTFeatures") -> Dict[str, float]:
        d = {}
        for key in self.SCALAR_FEATURES:
            val = getattr(features, key, 0.0)
            d[key] = float(val) if val is not None else 0.0
        return d

    def _compute_derived(self, raw: Dict[str, float]) -> Dict[str, float]:
        d = {}
        d["early_return_ratio"] = (
            raw["early_return_count"] / max(raw["return_statement_count"], 1)
        )
        d["exception_to_try_ratio"] = (
            raw["except_count"] / max(raw["try_count"], 1)
        )
        d["comment_to_code_ratio"] = (
            raw["comment_count"] / max(raw["line_count"], 1)
        )
        d["control_flow_density"] = (
            (raw["if_count"] + raw["for_count"] + raw["while_count"])
            / max(raw["line_count"], 1)
        )
        d["abstraction_density"] = (
            (raw["lambda_count"] + raw["closure_count"])
            / max(raw["line_count"], 1)
        )
        d["mutation_ratio"] = (
            raw["augmented_assignment_count"] / max(raw["assignment_count"], 1)
        )
        d["call_to_line_ratio"] = (
            raw["function_call_count"] / max(raw["line_count"], 1)
        )
        return d

    def _encode_libraries(self, libs: List[str]) -> np.ndarray:
        """
        Produce a fixed-length library signature vector.
        Uses consistent hashing to map library names to 64 buckets.
        """
        vec = np.zeros(64, dtype=np.float32)
        for lib in libs:
            bucket = int(hashlib.md5(lib.encode()).hexdigest(), 16) % 64
            vec[bucket] += 1.0
        return vec / max(vec.sum(), 1.0)  # L1-normalize

4.4 StyleDNA Fingerprint Engine

Purpose: Build a statistical model of the user's personal coding style — the "StyleDNA" — from the collected feature vectors. Support multiple style modes (clusters) and evolve over time.

Python

# fingerprint/builder.py

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
from sklearn.covariance import MinCovDet  # Robust estimator
from scipy.spatial.distance import mahalanobis
import pickle
import json


@dataclass
class StyleCluster:
    """A single mode within the user's style space."""
    cluster_id: int
    label: str                    # "production_python", "test_code", etc. (auto or user-named)
    language: str
    mean_vector: np.ndarray
    covariance_matrix: np.ndarray
    robust_covariance: np.ndarray  # MinCovDet estimate
    sample_count: int
    representative_functions: List[str]   # function names closest to centroid
    feature_names: List[str]
    top_distinguishing_features: List[str]  # Features that define this cluster


@dataclass
class StyleDNA:
    """
    The complete fingerprint for a user.
    Contains per-language, per-cluster distributions.
    """
    owner_email: str
    built_at: float           # epoch
    languages: List[str]
    clusters: List[StyleCluster]
    global_mean: Dict[str, np.ndarray]        # {language: mean_vector}
    global_covariance: Dict[str, np.ndarray]  # {language: cov_matrix}
    global_robust_cov: Dict[str, np.ndarray]  # {language: robust cov}
    total_samples: int
    version: str = "1.0"


class FingerprintBuilder:
    def __init__(self, vectors_by_language: Dict[str, List["StyleVector"]]):
        self.vectors = vectors_by_language

    def build(self, owner_email: str) -> StyleDNA:
        global_mean = {}
        global_cov = {}
        global_robust_cov = {}
        all_clusters = []

        for lang, vecs in self.vectors.items():
            if len(vecs) < 20:
                # Not enough samples to build a reliable baseline for this language
                continue

            matrix = np.stack([v.vector for v in vecs])

            # Global distribution
            global_mean[lang] = np.mean(matrix, axis=0)
            global_cov[lang] = np.cov(matrix.T) + np.eye(matrix.shape[1]) * 1e-6
            try:
                mcd = MinCovDet(support_fraction=0.75).fit(matrix)
                global_robust_cov[lang] = mcd.covariance_
            except Exception:
                global_robust_cov[lang] = global_cov[lang]

        return StyleDNA(
            owner_email=owner_email,
            built_at=__import__("time").time(),
            languages=list(global_mean.keys()),
            clusters=all_clusters,
            global_mean=global_mean,
            global_covariance=global_cov,
            global_robust_cov=global_robust_cov,
            total_samples=sum(len(v) for v in self.vectors.values()),
        )

4.5 Clusterer (UMAP + HDBSCAN)

Purpose: Discover multiple style "voices" within the user's codebase — e.g., test code vs. production code, scripting vs. library code — without requiring the user to label them manually.

Python

# fingerprint/clusterer.py

import numpy as np
import umap
import hdbscan
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class ClusteringResult:
    umap_2d: np.ndarray            # For visualization only
    umap_nd: np.ndarray            # Higher-dim for scoring (n_components=10)
    cluster_labels: np.ndarray     # -1 = noise/outlier
    cluster_probabilities: np.ndarray
    n_clusters: int
    noise_ratio: float
    cluster_sizes: Dict[int, int]


class StyleClusterer:
    """
    IMPORTANT: UMAP is used for two distinct purposes here:
    1. 2D visualization (n_components=2) — for the dashboard style map
    2. Compressed representation (n_components=10) for HDBSCAN clustering

    Scoring and anomaly detection happen in the ORIGINAL feature space,
    NOT in the UMAP-compressed space. UMAP can distort distances.
    """

    def __init__(
        self,
        umap_viz_components: int = 2,
        umap_model_components: int = 10,
        min_cluster_size: int = 15,
        min_samples: int = 5,
    ):
        self.umap_viz = umap.UMAP(
            n_components=umap_viz_components,
            n_neighbors=15,
            min_dist=0.1,
            metric="euclidean",
            random_state=42,
        )
        self.umap_model = umap.UMAP(
            n_components=umap_model_components,
            n_neighbors=15,
            min_dist=0.0,
            metric="euclidean",
            random_state=42,
        )
        self.hdbscan = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            cluster_selection_method="eom",
            prediction_data=True,   # Required for approximate_predict on new samples
        )

    def fit(self, matrix: np.ndarray) -> ClusteringResult:
        # Visualization projection (2D — do NOT use for scoring)
        umap_2d = self.umap_viz.fit_transform(matrix)

        # Model projection (10D — used for clustering only)
        umap_nd = self.umap_model.fit_transform(matrix)

        # Cluster in the 10D space
        labels, probs = hdbscan.approximate_predict(
            self.hdbscan.fit(umap_nd), umap_nd
        )

        sizes = {}
        for label in labels:
            if label >= 0:
                sizes[label] = sizes.get(label, 0) + 1

        return ClusteringResult(
            umap_2d=umap_2d,
            umap_nd=umap_nd,
            cluster_labels=labels,
            cluster_probabilities=probs,
            n_clusters=len(sizes),
            noise_ratio=float((labels == -1).sum()) / len(labels),
            cluster_sizes=sizes,
        )

    def predict_cluster(self, new_vector: np.ndarray) -> Tuple[int, float]:
        """
        Predict the closest cluster for a new sample.
        Returns (cluster_id, membership_probability).
        Note: Uses the HDBSCAN approximate_predict — NOT UMAP distances.
        """
        vec_nd = self.umap_model.transform(new_vector.reshape(1, -1))
        labels, probs = hdbscan.approximate_predict(self.hdbscan, vec_nd)
        return int(labels[0]), float(probs[0])

4.6 Immune System Scanner (Rust)

Purpose: A high-performance Rust binary responsible for the "hot path" — fast file enumeration, incremental change detection, and dispatching snippets to the Python scoring service. Modeled on ripgrep's design philosophy: respect .gitignore, maximize throughput, minimize latency.

Rust

// immune_system/scanner/src/main.rs

use std::path::{Path, PathBuf};
use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use ignore::WalkBuilder;
use tokio::sync::mpsc;
use reqwest::Client;

#[derive(Debug, Serialize)]
pub struct ScanRequest {
    pub file_path: String,
    pub language: String,
    pub content: String,
    pub trigger: ScanTrigger,
    pub baseline_version: String,
}

#[derive(Debug, Serialize)]
pub enum ScanTrigger {
    PreCommit,
    IDESave,
    CLIAdHoc,
    CICheck,
}

#[derive(Debug, Deserialize)]
pub struct ScanResponse {
    pub overall_match_pct: f32,
    pub verdict: Verdict,
    pub suspicious_functions: Vec<SuspiciousFunction>,
    pub explanation: String,
    pub confidence: f32,
}

#[derive(Debug, Deserialize)]
pub enum Verdict {
    Match,
    Warn,
    Block,
    Insufficient, // Not enough baseline data for this language
}

#[derive(Debug, Deserialize)]
pub struct SuspiciousFunction {
    pub name: String,
    pub start_line: usize,
    pub end_line: usize,
    pub match_pct: f32,
    pub top_deviations: Vec<String>,
}

pub struct Scanner {
    api_base: String,
    client: Client,
    language_map: HashMap<String, String>,
}

impl Scanner {
    pub fn new(api_base: &str) -> Self {
        let mut language_map = HashMap::new();
        language_map.insert("py".to_string(), "python".to_string());
        language_map.insert("go".to_string(), "go".to_string());
        language_map.insert("js".to_string(), "javascript".to_string());
        language_map.insert("ts".to_string(), "typescript".to_string());
        language_map.insert("rs".to_string(), "rust".to_string());
        language_map.insert("java".to_string(), "java".to_string());

        Scanner {
            api_base: api_base.to_string(),
            client: Client::new(),
            language_map,
        }
    }

    pub async fn scan_directory(&self, root: &Path) -> Vec<ScanResponse> {
        let (tx, mut rx) = mpsc::channel(128);

        // Walk directory respecting .gitignore, .ignore files
        let walker = WalkBuilder::new(root)
            .git_ignore(true)
            .git_exclude(true)
            .hidden(false)
            .build_parallel();

        walker.run(|| {
            let tx = tx.clone();
            let language_map = self.language_map.clone();
            Box::new(move |result| {
                if let Ok(entry) = result {
                    let path = entry.path().to_path_buf();
                    if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
                        if language_map.contains_key(ext) {
                            let _ = tx.blocking_send(path);
                        }
                    }
                }
                ignore::WalkState::Continue
            })
        });

        drop(tx);

        let mut results = Vec::new();
        while let Some(path) = rx.recv().await {
            if let Ok(resp) = self.scan_file(&path, ScanTrigger::CLIAdHoc).await {
                results.push(resp);
            }
        }
        results
    }

    pub async fn scan_file(
        &self,
        path: &Path,
        trigger: ScanTrigger,
    ) -> Result<ScanResponse, Box<dyn std::error::Error>> {
        let ext = path.extension()
            .and_then(|e| e.to_str())
            .unwrap_or("");
        let language = self.language_map.get(ext)
            .cloned()
            .unwrap_or_else(|| "unknown".to_string());

        let content = tokio::fs::read_to_string(path).await?;

        let request = ScanRequest {
            file_path: path.to_string_lossy().to_string(),
            language,
            content,
            trigger,
            baseline_version: self.get_baseline_version().await?,
        };

        let response = self.client
            .post(format!("{}/api/v1/scan/file", self.api_base))
            .json(&request)
            .send()
            .await?
            .json::<ScanResponse>()
            .await?;

        Ok(response)
    }

    async fn get_baseline_version(&self) -> Result<String, Box<dyn std::error::Error>> {
        let resp = self.client
            .get(format!("{}/api/v1/fingerprint/version", self.api_base))
            .send()
            .await?
            .json::<serde_json::Value>()
            .await?;
        Ok(resp["version"].as_str().unwrap_or("unknown").to_string())
    }
}

4.7 Scorer & Localizer

Purpose: Given a new code sample's feature vector and the user's StyleDNA, compute a match score and identify which specific functions within a file are most anomalous.

Python

# immune_system/scorer.py

import numpy as np
from scipy.spatial.distance import mahalanobis
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FunctionScore:
    function_name: str
    start_line: int
    end_line: int
    raw_distance: float       # Mahalanobis distance from baseline
    match_pct: float          # 0-100, inverse of normalized distance
    cluster_assignment: int   # Which voice does this match?
    cluster_confidence: float
    is_suspicious: bool


@dataclass
class FileScore:
    file_path: str
    language: str
    overall_match_pct: float
    function_scores: List[FunctionScore]
    verdict: str              # MATCH | WARN | BLOCK | INSUFFICIENT
    confidence: float
    suspicious_function_count: int


class StyleScorer:
    """
    Scores new code against the user's StyleDNA baseline.

    Key design decisions:
    1. Scoring happens in the ORIGINAL feature space (not UMAP compressed).
    2. We use Mahalanobis distance, which accounts for feature correlations
       and different scales — unlike Euclidean distance.
    3. For multi-cluster baselines, we take the MINIMUM distance to any
       cluster (best-case match) before flagging.
    4. We apply a calibration curve trained on held-out "self" samples
       to produce a calibrated probability rather than a raw distance.
    """

    def __init__(self, dna: "StyleDNA", config: "ScoringConfig"):
        self.dna = dna
        self.config = config

    def score_function(
        self,
        vector: np.ndarray,
        language: str,
    ) -> Tuple[float, float]:
        """
        Returns (match_pct: 0-100, confidence: 0-1).
        """
        if language not in self.dna.global_mean:
            return 50.0, 0.0  # Insufficient baseline; return neutral

        # Use robust covariance if available (more resistant to outliers in training data)
        cov = self.dna.global_robust_cov.get(language, self.dna.global_covariance[language])
        mean = self.dna.global_mean[language]

        try:
            cov_inv = np.linalg.pinv(cov)  # Pseudo-inverse for stability
            dist = mahalanobis(vector, mean, cov_inv)
        except np.linalg.LinAlgError:
            # Fallback: normalized Euclidean
            std = np.std(np.stack([mean]), axis=0) + 1e-8
            dist = float(np.linalg.norm((vector - mean) / std))

        # If the user has multiple clusters, use the best (minimum) distance
        if self.dna.clusters:
            cluster_distances = []
            for cluster in self.dna.clusters:
                if cluster.language != language:
                    continue
                try:
                    cov_inv = np.linalg.pinv(cluster.robust_covariance)
                    d = mahalanobis(vector, cluster.mean_vector, cov_inv)
                    cluster_distances.append(d)
                except Exception:
                    pass
            if cluster_distances:
                dist = min(dist, min(cluster_distances))

        # Convert distance to a 0-100 match percentage via sigmoid-like mapping
        # Empirically calibrated: distance of 3.0 ≈ 50% match
        match_pct = 100.0 / (1.0 + (dist / 3.0) ** 2)

        # Confidence is a function of how many training samples we have
        sample_count = self.dna.total_samples
        confidence = min(1.0, sample_count / 500.0)  # Full confidence at 500+ samples

        return float(match_pct), float(confidence)

    def score_file(
        self,
        function_vectors: List[Tuple["FunctionNode", np.ndarray]],
        language: str,
        file_path: str,
    ) -> FileScore:
        fn_scores = []
        for fn_node, vector in function_vectors:
            match_pct, confidence = self.score_function(vector, language)
            fn_score = FunctionScore(
                function_name=fn_node.name,
                start_line=fn_node.start_line,
                end_line=fn_node.end_line,
                raw_distance=0.0,  # Set during scoring
                match_pct=match_pct,
                cluster_assignment=-1,
                cluster_confidence=confidence,
                is_suspicious=match_pct < self.config.warn_threshold,
            )
            fn_scores.append(fn_score)

        if not fn_scores:
            return FileScore(file_path, language, 100.0, [], "MATCH", 0.0, 0)

        # File-level score is the weighted average (by line count)
        weights = [fn.end_line - fn.start_line + 1 for fn, _ in function_vectors]
        overall = float(np.average([s.match_pct for s in fn_scores], weights=weights))

        suspicious_count = sum(1 for s in fn_scores if s.is_suspicious)

        if overall >= self.config.match_threshold:
            verdict = "MATCH"
        elif overall >= self.config.warn_threshold:
            verdict = "WARN"
        else:
            verdict = "BLOCK" if self.config.enable_blocking else "WARN"

        avg_confidence = float(np.mean([s.cluster_confidence for s in fn_scores]))

        return FileScore(
            file_path=file_path,
            language=language,
            overall_match_pct=overall,
            function_scores=fn_scores,
            verdict=verdict,
            confidence=avg_confidence,
            suspicious_function_count=suspicious_count,
        )

4.8 Explainer Engine

Purpose: For any flagged code, generate a plain-language explanation grounded in the user's own baseline statistics — not vague AI-sounding outputs, but specific, quantified feature deltas.

Python

# immune_system/explainer.py

import numpy as np
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class FeatureDelta:
    feature_name: str
    your_typical_value: float
    this_code_value: float
    z_score: float             # How many std devs away from your mean
    direction: str             # "higher" or "lower"
    human_description: str


@dataclass
class Explanation:
    summary: str
    top_deltas: List[FeatureDelta]
    style_voice_mismatch: str   # e.g. "This looks more like test code than production code"
    nearest_cluster: str
    raw_match_pct: float


# Human-readable templates for each feature
FEATURE_DESCRIPTIONS = {
    "line_count": {
        "higher": "This function is {val:.0f} lines long. Your functions typically average {typical:.0f} lines.",
        "lower": "This function is only {val:.0f} lines. Your functions typically average {typical:.0f} lines.",
    },
    "max_nesting_depth": {
        "higher": "Maximum nesting depth is {val:.0f}. You typically nest at most {typical:.0f} levels deep.",
        "lower": "Nesting depth is {val:.0f}. You typically go deeper ({typical:.0f} levels).",
    },
    "early_return_count": {
        "higher": "Contains {val:.0f} early returns. You rarely use early returns (avg {typical:.2f}).",
        "lower": "No early returns detected. You typically use {typical:.2f} early returns per function.",
    },
    "comment_to_code_ratio": {
        "higher": "Comment density is {val:.2f} (comments per line). Yours is typically {typical:.2f}.",
        "lower": "Very few comments ({val:.2f} ratio). You typically comment at {typical:.2f} ratio.",
    },
    "comprehension_count": {
        "higher": "Uses {val:.0f} comprehensions. You rarely use comprehensions (avg {typical:.2f}).",
        "lower": "No comprehensions. You typically use {typical:.2f} comprehensions per function.",
    },
    "try_count": {
        "higher": "Contains {val:.0f} try blocks. Your functions average {typical:.2f} try blocks.",
        "lower": "No exception handling. You typically use {typical:.2f} try blocks per function.",
    },
    "chained_call_depth": {
        "higher": "Method chain depth is {val:.0f}. You typically chain at most {typical:.0f} deep.",
        "lower": "No chaining detected. You typically chain {typical:.0f} levels deep.",
    },
    "lambda_count": {
        "higher": "Contains {val:.0f} lambdas. You almost never use lambdas (avg {typical:.2f}).",
        "lower": "No lambdas. You typically use {typical:.2f} per function.",
    },
    "name_is_snake_case": {
        "higher": "Function uses snake_case naming. Your functions are typically not snake_case.",
        "lower": "Function is not snake_case. You almost always use snake_case.",
    },
    "param_count": {
        "higher": "Has {val:.0f} parameters. Your functions typically have {typical:.0f}.",
        "lower": "Has only {val:.0f} parameters. Your functions typically have {typical:.0f}.",
    },
}


class ExplainerEngine:
    def __init__(self, dna: "StyleDNA"):
        self.dna = dna

    def explain(
        self,
        raw_features: Dict[str, float],
        vector: np.ndarray,
        language: str,
        match_pct: float,
        cluster_id: int = -1,
    ) -> Explanation:
        if language not in self.dna.global_mean:
            return Explanation(
                summary="Insufficient baseline data for this language.",
                top_deltas=[],
                style_voice_mismatch="",
                nearest_cluster="unknown",
                raw_match_pct=match_pct,
            )

        mean = self.dna.global_mean[language]
        cov = self.dna.global_covariance[language]
        std = np.sqrt(np.diag(cov)) + 1e-8

        # Compute per-feature z-scores
        deltas: List[FeatureDelta] = []
        feature_names = list(raw_features.keys())

        for i, (feature_name, value) in enumerate(raw_features.items()):
            if i >= len(mean):
                break
            typical = mean[i]
            std_val = std[i]
            z = (value - typical) / std_val
            if abs(z) < 1.5:
                continue  # Only report meaningfully deviant features

            direction = "higher" if value > typical else "lower"
            template = FEATURE_DESCRIPTIONS.get(feature_name, {}).get(direction)
            if template:
                human_desc = template.format(val=value, typical=typical)
            else:
                human_desc = (
                    f"{feature_name}: {value:.2f} vs your typical {typical:.2f} "
                    f"(z={z:+.1f})"
                )

            deltas.append(FeatureDelta(
                feature_name=feature_name,
                your_typical_value=float(typical),
                this_code_value=float(value),
                z_score=float(z),
                direction=direction,
                human_description=human_desc,
            ))

        # Sort by absolute z-score descending, take top 5
        deltas.sort(key=lambda d: abs(d.z_score), reverse=True)
        top_deltas = deltas[:5]

        summary = self._build_summary(match_pct, top_deltas, language)
        voice_mismatch = self._assess_voice_mismatch(cluster_id, language)

        return Explanation(
            summary=summary,
            top_deltas=top_deltas,
            style_voice_mismatch=voice_mismatch,
            nearest_cluster=self._cluster_name(cluster_id),
            raw_match_pct=match_pct,
        )

    def _build_summary(self, match_pct: float, deltas: List[FeatureDelta], lang: str) -> str:
        if match_pct >= 80:
            return f"This {lang} code matches your style well ({match_pct:.0f}% match)."
        elif match_pct >= 50:
            primary = deltas[0].human_description if deltas else "several style differences detected"
            return (
                f"Partial style match ({match_pct:.0f}%). "
                f"Most notable difference: {primary}"
            )
        else:
            primary = deltas[0].human_description if deltas else "significant style differences"
            return (
                f"Low style match ({match_pct:.0f}%). "
                f"This code differs substantially from your historical patterns. "
                f"Biggest divergence: {primary}"
            )

    def _assess_voice_mismatch(self, cluster_id: int, language: str) -> str:
        if cluster_id < 0 or not self.dna.clusters:
            return ""
        matching = [c for c in self.dna.clusters if c.cluster_id == cluster_id]
        if matching:
            return f"Closest match to your '{matching[0].label}' style cluster."
        return ""

    def _cluster_name(self, cluster_id: int) -> str:
        for c in self.dna.clusters:
            if c.cluster_id == cluster_id:
                return c.label
        return "unknown"

4.9 Evolution Tracker

Purpose: Track how the user's coding style changes over time. Detect "style eras," quantify drift per feature, and generate a timeline report.

Python

# evolution/timeline.py

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime


@dataclass
class StyleEra:
    """A coherent period during which the user's style was relatively stable."""
    era_id: int
    start_date: datetime
    end_date: datetime
    label: str              # e.g. "Pre-Python-3.10", "After-switching-to-Go", etc.
    dominant_cluster_id: int
    representative_features: Dict[str, float]
    sample_count: int


@dataclass
class FeatureDrift:
    feature_name: str
    values_by_quarter: Dict[str, float]    # {"2022-Q1": 2.3, ...}
    trend: str                             # "increasing" | "decreasing" | "stable"
    drift_magnitude: float                 # total change over observed period
    change_point_quarters: List[str]       # Quarters where significant shifts occurred


@dataclass
class EvolutionReport:
    owner_email: str
    languages_analyzed: List[str]
    total_time_span_days: int
    eras: List[StyleEra]
    feature_drifts: List[FeatureDrift]
    style_stability_score: float           # 0-1: how consistent is the style?
    biggest_single_shift: str              # Plain language description
    narrative: str                         # Multi-sentence summary


class StyleEvolutionTracker:
    def __init__(self, db: "Database"):
        self.db = db

    def compute_evolution(self, language: str, owner_email: str) -> EvolutionReport:
        samples = self.db.get_samples_with_vectors(language=language, owner=owner_email)
        if len(samples) < 50:
            return self._insufficient_data_report(language, owner_email)

        df = self._to_dataframe(samples)
        df["quarter"] = pd.PeriodIndex(df["timestamp"], freq="Q").astype(str)

        feature_drifts = []
        scalar_features = self._get_scalar_feature_names()

        for feature in scalar_features:
            if feature not in df.columns:
                continue
            quarterly = df.groupby("quarter")[feature].mean().to_dict()
            drift = self._analyze_drift(feature, quarterly)
            if drift.drift_magnitude > 0.1:  # Only report meaningful drifts
                feature_drifts.append(drift)

        feature_drifts.sort(key=lambda d: d.drift_magnitude, reverse=True)

        eras = self._detect_eras(df, feature_drifts)
        stability = self._compute_stability(df, scalar_features)
        narrative = self._build_narrative(language, eras, feature_drifts[:3], stability)

        first_ts = df["timestamp"].min()
        last_ts = df["timestamp"].max()
        span_days = (last_ts - first_ts).days

        biggest = feature_drifts[0].feature_name if feature_drifts else "no significant drift"

        return EvolutionReport(
            owner_email=owner_email,
            languages_analyzed=[language],
            total_time_span_days=span_days,
            eras=eras,
            feature_drifts=feature_drifts[:10],
            style_stability_score=stability,
            biggest_single_shift=biggest,
            narrative=narrative,
        )

    def _analyze_drift(self, feature: str, quarterly: Dict[str, float]) -> FeatureDrift:
        if len(quarterly) < 2:
            return FeatureDrift(feature, quarterly, "stable", 0.0, [])

        values = list(quarterly.values())
        quarters = list(quarterly.keys())
        total_drift = abs(values[-1] - values[0]) / (abs(values[0]) + 1e-8)

        # Simple trend detection
        slope = np.polyfit(range(len(values)), values, 1)[0]
        if slope > 0.05:
            trend = "increasing"
        elif slope < -0.05:
            trend = "decreasing"
        else:
            trend = "stable"

        # Detect change points using a simple sliding window
        change_points = []
        window = 2
        for i in range(window, len(values) - window):
            before = np.mean(values[i - window:i])
            after = np.mean(values[i:i + window])
            if abs(after - before) > 0.5 * np.std(values):
                change_points.append(quarters[i])

        return FeatureDrift(
            feature_name=feature,
            values_by_quarter=quarterly,
            trend=trend,
            drift_magnitude=float(total_drift),
            change_point_quarters=change_points,
        )

    def _compute_stability(self, df: pd.DataFrame, features: List[str]) -> float:
        """Stability score: 1 = perfectly consistent style, 0 = highly variable."""
        valid_features = [f for f in features if f in df.columns]
        if not valid_features:
            return 1.0
        quarterly_stds = []
        for feat in valid_features:
            qstd = df.groupby(df["timestamp"].dt.to_period("Q"))[feat].mean().std()
            quarterly_stds.append(qstd if not np.isnan(qstd) else 0.0)
        avg_std = float(np.mean(quarterly_stds))
        # Map to 0-1: std of 0 = 1.0 stability, std of 2.0 = 0.0 stability
        return float(max(0.0, 1.0 - avg_std / 2.0))

    def _to_dataframe(self, samples) -> pd.DataFrame:
        rows = []
        for s in samples:
            row = {"timestamp": s.timestamp, **s.raw_features}
            rows.append(row)
        return pd.DataFrame(rows)

    def _detect_eras(self, df, drifts) -> List[StyleEra]:
        # Simplified: use change point quarters as era boundaries
        change_quarters = set()
        for drift in drifts[:3]:
            change_quarters.update(drift.change_point_quarters)
        # Build eras from sorted change points
        # (full implementation uses ruptures or PELT for proper change point detection)
        return []

    def _build_narrative(self, lang, eras, top_drifts, stability) -> str:
        stability_word = "very stable" if stability > 0.8 else "moderately stable" if stability > 0.5 else "evolving significantly"
        drift_descriptions = [f"{d.feature_name} ({d.trend})" for d in top_drifts]
        drifts_str = ", ".join(drift_descriptions) if drift_descriptions else "no major features"
        return (
            f"Your {lang} style has been {stability_word} over the observed period. "
            f"The most notable changes are in: {drifts_str}. "
            f"Detected {len(eras)} distinct style era(s)."
        )

    def _get_scalar_feature_names(self) -> List[str]:
        from analyzer.feature_builder import FeatureVectorBuilder
        return FeatureVectorBuilder.SCALAR_FEATURES + FeatureVectorBuilder.DERIVED_FEATURES

    def _insufficient_data_report(self, language, owner_email) -> EvolutionReport:
        return EvolutionReport(
            owner_email=owner_email,
            languages_analyzed=[language],
            total_time_span_days=0,
            eras=[],
            feature_drifts=[],
            style_stability_score=1.0,
            biggest_single_shift="Insufficient data",
            narrative=f"Not enough {language} samples to compute evolution (minimum 50 required).",
        )

4.10 Integration Layer

Pre-commit Git Hook:

Bash

#!/bin/bash
# .git/hooks/pre-commit
# Installed by `codedna install-hook`

set -e

CODEDNA_API="http://127.0.0.1:7432"

# Check if the API server is running
if ! curl -s --max-time 1 "$CODEDNA_API/api/v1/health" > /dev/null 2>&1; then
    echo "ℹ️  CodeDNA: Server not running. Skipping style check."
    exit 0
fi

# Get list of staged files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

if [ -z "$STAGED_FILES" ]; then
    exit 0
fi

# Send staged files to CodeDNA scanner
RESULT=$(echo "$STAGED_FILES" | xargs -I{} curl -s -X POST \
    "$CODEDNA_API/api/v1/scan/file" \
    -H "Content-Type: application/json" \
    -d "{\"file_path\": \"{}\", \"trigger\": \"pre_commit\", \
         \"content\": \"$(git show :{}  | base64 -w0)\"}")

# Parse verdict
VERDICT=$(echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('results', [])
any_block = any(r['verdict'] == 'BLOCK' for r in results)
any_warn = any(r['verdict'] == 'WARN' for r in results)
if any_block:
    print('BLOCK')
elif any_warn:
    print('WARN')
else:
    print('PASS')
")

case "$VERDICT" in
    PASS)
        echo "🧬 CodeDNA: Style check passed."
        ;;
    WARN)
        echo ""
        echo "⚠️  CodeDNA: Style anomaly detected in staged files."
        echo "$RESULT" | python3 -m codedna.format_hook_output
        echo ""
        echo "Commit proceeding (run 'codedna explain <file>' for details)."
        ;;
    BLOCK)
        echo ""
        echo "🚫 CodeDNA: Commit blocked — significant style mismatch detected."
        echo "$RESULT" | python3 -m codedna.format_hook_output
        echo ""
        echo "To override: git commit --no-verify"
        echo "To inspect:  codedna explain <file>"
        exit 1
        ;;
esac

VS Code Extension (TypeScript):

TypeScript

// integrations/vscode/src/extension.ts

import * as vscode from 'vscode';
import axios from 'axios';

const API_BASE = 'http://127.0.0.1:7432';
const CODEDNA_DECORATION = vscode.window.createTextEditorDecorationType({
    backgroundColor: 'rgba(255, 165, 0, 0.15)',
    borderColor: 'rgba(255, 165, 0, 0.6)',
    borderWidth: '0 0 0 3px',
    borderStyle: 'solid',
});

export function activate(context: vscode.ExtensionContext) {
    // Debounced scan on save
    vscode.workspace.onDidSaveTextDocument(
        debounce(async (doc: vscode.TextDocument) => {
            const result = await scanFile(doc.fileName, doc.getText(), doc.languageId);
            if (!result) return;
            displayResults(result, doc);
        }, 800),
        null,
        context.subscriptions
    );

    // Command: explain current function
    context.subscriptions.push(
        vscode.commands.registerCommand('codedna.explainFunction', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const line = editor.selection.active.line;
            await showExplanation(editor.document, line);
        })
    );
}

async function scanFile(
    filePath: string,
    content: string,
    languageId: string
): Promise<ScanResponse | null> {
    try {
        const resp = await axios.post(`${API_BASE}/api/v1/scan/file`, {
            file_path: filePath,
            content: content,
            language: languageId,
            trigger: 'ide_save',
        }, { timeout: 2000 });
        return resp.data as ScanResponse;
    } catch {
        return null;
    }
}

function displayResults(result: ScanResponse, doc: vscode.TextDocument) {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document !== doc) return;

    const decorations: vscode.DecorationOptions[] = [];

    for (const fn of result.suspicious_functions) {
        const range = new vscode.Range(
            new vscode.Position(fn.start_line - 1, 0),
            new vscode.Position(fn.end_line - 1, 9999)
        );
        decorations.push({
            range,
            hoverMessage: new vscode.MarkdownString(
                `**🧬 CodeDNA:** ${fn.match_pct.toFixed(0)}% style match\n\n` +
                fn.top_deviations.map(d => `- ${d}`).join('\n')
            ),
        });
    }

    editor.setDecorations(CODEDNA_DECORATION, decorations);

    // Status bar
    const statusItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right, 100
    );
    statusItem.text = result.overall_match_pct >= 75
        ? `🧬 ${result.overall_match_pct.toFixed(0)}%`
        : `⚠️ ${result.overall_match_pct.toFixed(0)}%`;
    statusItem.tooltip = result.suspicious_functions.length > 0
        ? `${result.suspicious_functions.length} suspicious function(s) detected`
        : 'Style matches your baseline';
    statusItem.show();
}

function debounce(fn: (...args: any[]) => void, delay: number) {
    let timer: NodeJS.Timeout;
    return (...args: any[]) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

interface ScanResponse {
    overall_match_pct: number;
    verdict: string;
    suspicious_functions: Array<{
        name: string;
        start_line: number;
        end_line: number;
        match_pct: number;
        top_deviations: string[];
    }>;
    explanation: string;
}

4.11 Local API Server

Purpose: FastAPI server at http://127.0.0.1:7432 bridging the Rust scanner, Python pipeline, VS Code extension, CLI, and dashboard.

Python

# api/server.py

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import json

from immune_system.scorer import StyleScorer
from immune_system.explainer import ExplainerEngine
from analyzer.ast_extractor import ASTExtractor
from analyzer.feature_builder import FeatureVectorBuilder
from fingerprint.builder import StyleDNA
from storage.db import Database
from events import EventBus


app = FastAPI(title="CodeDNA Local API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:7432"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency injection (set at startup)
_dna: Optional[StyleDNA] = None
_scorer: Optional[StyleScorer] = None
_explainer: Optional[ExplainerEngine] = None
_db: Optional[Database] = None
_event_bus: Optional[EventBus] = None


class ScanFileRequest(BaseModel):
    file_path: str
    content: str
    language: str
    trigger: str = "cli"
    baseline_version: Optional[str] = None


class ScanFileResponse(BaseModel):
    overall_match_pct: float
    verdict: str
    confidence: float
    suspicious_functions: List[dict]
    explanation: str
    feature_deltas: List[dict]


@app.post("/api/v1/scan/file", response_model=ScanFileResponse)
async def scan_file(req: ScanFileRequest, bg: BackgroundTasks):
    if _dna is None:
        raise HTTPException(503, "Fingerprint not yet built. Run `codedna init` first.")

    extractor = ASTExtractor()
    builder = FeatureVectorBuilder()

    functions = extractor.extract_functions(req.content, req.language)
    if not functions:
        return ScanFileResponse(
            overall_match_pct=100.0,
            verdict="MATCH",
            confidence=0.0,
            suspicious_functions=[],
            explanation="No scoreable functions found in this file.",
            feature_deltas=[],
        )

    function_vectors = []
    for fn in functions:
        features = extractor.extract_features(fn, req.language)
        vector = builder.build(features, _make_dummy_sample(req, fn))
        function_vectors.append((fn, vector.vector, features, vector.raw))

    file_score = _scorer.score_file(
        [(fn, vec) for fn, vec, _, _ in function_vectors],
        req.language,
        req.file_path,
    )

    # Explain the most suspicious function (if any)
    explanation_text = ""
    all_deltas = []
    if file_score.suspicious_function_count > 0:
        worst = min(file_score.function_scores, key=lambda s: s.match_pct)
        worst_idx = next(
            i for i, (fn, _, _, _) in enumerate(function_vectors)
            if fn.name == worst.function_name
        )
        _, _, worst_features_obj, worst_raw = function_vectors[worst_idx]
        explanation = _explainer.explain(
            worst_raw, function_vectors[worst_idx][1],
            req.language, worst.match_pct,
        )
        explanation_text = explanation.summary
        all_deltas = [
            {
                "feature": d.feature_name,
                "yours": d.your_typical_value,
                "this_code": d.this_code_value,
                "z_score": d.z_score,
                "description": d.human_description,
            }
            for d in explanation.top_deltas
        ]

    # Persist to DB (background, non-blocking)
    bg.add_task(_persist_scan_result, file_score, req)

    # Emit SSE event
    bg.add_task(_event_bus.publish, {
        "type": "scan_complete",
        "file": req.file_path,
        "verdict": file_score.verdict,
        "match_pct": file_score.overall_match_pct,
    })

    return ScanFileResponse(
        overall_match_pct=file_score.overall_match_pct,
        verdict=file_score.verdict,
        confidence=file_score.confidence,
        suspicious_functions=[
            {
                "name": s.function_name,
                "start_line": s.start_line,
                "end_line": s.end_line,
                "match_pct": s.match_pct,
                "top_deviations": [],  # Populated by explainer per-function in v1.1
            }
            for s in file_score.function_scores if s.is_suspicious
        ],
        explanation=explanation_text,
        feature_deltas=all_deltas,
    )


@app.get("/api/v1/stream/events")
async def stream_events():
    async def event_generator():
        queue = _event_bus.subscribe()
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"
        finally:
            _event_bus.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/v1/health")
async def health():
    return {
        "status": "ok",
        "fingerprint_built": _dna is not None,
        "languages": _dna.languages if _dna else [],
        "total_samples": _dna.total_samples if _dna else 0,
        "version": "1.0.0",
    }

5. Data Models & Schemas
5.1 SQLite Schema

SQL

-- migrations/001_initial.sql

-- Raw code samples extracted from git history
CREATE TABLE IF NOT EXISTS code_samples (
    id              TEXT PRIMARY KEY,
    repo_path       TEXT NOT NULL,
    commit_sha      TEXT NOT NULL,
    author_email    TEXT NOT NULL,
    timestamp       DATETIME NOT NULL,
    file_path       TEXT NOT NULL,
    language        TEXT NOT NULL,
    function_name   TEXT NOT NULL,
    function_body   TEXT,
    start_line      INTEGER,
    end_line        INTEGER,
    line_count      INTEGER,
    is_new          BOOLEAN NOT NULL DEFAULT TRUE,
    commit_message  TEXT
);

-- Normalized feature vectors per sample
CREATE TABLE IF NOT EXISTS feature_vectors (
    id              TEXT PRIMARY KEY,
    sample_id       TEXT NOT NULL,
    language        TEXT NOT NULL,
    author_email    TEXT NOT NULL,
    timestamp       DATETIME NOT NULL,
    raw_features    TEXT NOT NULL,    -- JSON: {feature_name: value}
    vector_blob     BLOB NOT NULL,    -- NumPy float32 array, serialized
    cluster_id      INTEGER,          -- Assigned after clustering
    umap_x          REAL,             -- 2D visualization coordinate
    umap_y          REAL,
    vector_version  TEXT NOT NULL DEFAULT '1.0',
    FOREIGN KEY (sample_id) REFERENCES code_samples(id)
);

-- StyleDNA fingerprint snapshots
CREATE TABLE IF NOT EXISTS fingerprints (
    id              TEXT PRIMARY KEY,
    owner_email     TEXT NOT NULL,
    built_at        DATETIME NOT NULL,
    language        TEXT NOT NULL,
    total_samples   INTEGER NOT NULL,
    mean_vector     BLOB NOT NULL,      -- NumPy array
    cov_matrix      BLOB NOT NULL,      -- NumPy array
    robust_cov      BLOB NOT NULL,      -- MinCovDet output
    cluster_data    TEXT,               -- JSON: cluster definitions
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    version         TEXT NOT NULL DEFAULT '1.0'
);

-- Real-time scan results
CREATE TABLE IF NOT EXISTS scan_results (
    id              TEXT PRIMARY KEY,
    scanned_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    file_path       TEXT NOT NULL,
    language        TEXT NOT NULL,
    trigger         TEXT NOT NULL,      -- pre_commit|ide_save|cli|ci
    overall_match   REAL NOT NULL,
    verdict         TEXT NOT NULL,      -- MATCH|WARN|BLOCK|INSUFFICIENT
    confidence      REAL NOT NULL,
    suspicious_count INTEGER NOT NULL DEFAULT 0,
    explanation     TEXT,
    feature_deltas  TEXT,               -- JSON array
    function_scores TEXT,               -- JSON array
    fingerprint_id  TEXT,
    FOREIGN KEY (fingerprint_id) REFERENCES fingerprints(id)
);

-- Style evolution data (time-bucketed feature statistics)
CREATE TABLE IF NOT EXISTS evolution_buckets (
    id              TEXT PRIMARY KEY,
    owner_email     TEXT NOT NULL,
    language        TEXT NOT NULL,
    quarter         TEXT NOT NULL,       -- "2023-Q3"
    sample_count    INTEGER NOT NULL,
    feature_means   TEXT NOT NULL,       -- JSON: {feature: mean_value}
    feature_stds    TEXT NOT NULL,       -- JSON: {feature: std_value}
    cluster_distribution TEXT           -- JSON: {cluster_id: count}
);

-- Style era definitions (detected by evolution tracker)
CREATE TABLE IF NOT EXISTS style_eras (
    id              TEXT PRIMARY KEY,
    owner_email     TEXT NOT NULL,
    language        TEXT NOT NULL,
    start_date      DATETIME NOT NULL,
    end_date        DATETIME,
    label           TEXT NOT NULL,
    dominant_cluster INTEGER,
    notes           TEXT
);

-- User settings
CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Identity aliases (map multiple emails to one user)
CREATE TABLE IF NOT EXISTS identity_aliases (
    id              TEXT PRIMARY KEY,
    canonical_email TEXT NOT NULL,
    alias_email     TEXT NOT NULL,
    alias_name      TEXT,
    added_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Feedback (user marks a flag as correct or incorrect)
CREATE TABLE IF NOT EXISTS scan_feedback (
    id              TEXT PRIMARY KEY,
    scan_result_id  TEXT NOT NULL,
    feedback        TEXT NOT NULL,       -- "correct_flag"|"false_positive"|"true_positive"
    user_note       TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scan_result_id) REFERENCES scan_results(id)
);

-- Indexes
CREATE INDEX idx_samples_author        ON code_samples(author_email);
CREATE INDEX idx_samples_language      ON code_samples(language);
CREATE INDEX idx_samples_timestamp     ON code_samples(timestamp);
CREATE INDEX idx_vectors_author_lang   ON feature_vectors(author_email, language);
CREATE INDEX idx_vectors_cluster       ON feature_vectors(cluster_id);
CREATE INDEX idx_scans_timestamp       ON scan_results(scanned_at);
CREATE INDEX idx_scans_verdict         ON scan_results(verdict);
CREATE INDEX idx_evolution_quarter     ON evolution_buckets(owner_email, language, quarter);

6. API Specifications
6.1 Internal REST API

All endpoints served at http://127.0.0.1:7432/api/v1/

Scan Endpoints

text

POST   /api/v1/scan/file
       Body: { file_path, content, language, trigger }
       Returns: ScanFileResponse

POST   /api/v1/scan/diff
       Body: { diff_text, language, commit_message? }
       Returns: { functions_scanned, suspicious_functions[], overall_match_pct, verdict }

POST   /api/v1/scan/function
       Body: { function_body, language, function_name }
       Returns: { match_pct, verdict, explanation, feature_deltas[] }

GET    /api/v1/scan/history
       Query: ?limit=100&offset=0&verdict=&language=&from=&to=
       Returns: { total, items: ScanResult[] }

GET    /api/v1/scan/:id
       Returns: ScanResult (with full feature deltas and function scores)

POST   /api/v1/scan/:id/feedback
       Body: { feedback: "false_positive"|"correct_flag", note? }
       Returns: { success }

Fingerprint Endpoints

text

POST   /api/v1/fingerprint/build
       Body: { repo_path, author_emails[], rebuild?: bool }
       Returns: { job_id }           ← async; poll /jobs/:id

GET    /api/v1/fingerprint
       Returns: { languages, total_samples, built_at, clusters[], version }

GET    /api/v1/fingerprint/version
       Returns: { version: string }

GET    /api/v1/fingerprint/clusters
       Returns: Cluster[] (with umap_points for visualization)

PUT    /api/v1/fingerprint/clusters/:id/label
       Body: { label: string }
       Returns: { success }

DELETE /api/v1/fingerprint
       Returns: { success }    ← Deletes baseline and all vectors; requires confirmation

Evolution Endpoints

text

GET    /api/v1/evolution
       Query: ?language=python
       Returns: EvolutionReport

GET    /api/v1/evolution/timeline
       Query: ?language=python&feature=max_nesting_depth
       Returns: { quarter: value }[] ← timeseries data for charting

GET    /api/v1/evolution/eras
       Returns: StyleEra[]

POST   /api/v1/evolution/eras/:id/label
       Body: { label: string }
       Returns: { success }

Settings Endpoints

text

GET    /api/v1/settings
       Returns: Settings

PUT    /api/v1/settings
       Body: Partial<Settings>
       Returns: Settings

GET    /api/v1/identity
       Returns: { canonical_email, aliases[] }

POST   /api/v1/identity/alias
       Body: { email, name? }
       Returns: { success }

DELETE /api/v1/identity/alias/:email
       Returns: { success }

Job Endpoints (Async Operations)

text

GET    /api/v1/jobs/:id
       Returns: { status: "pending"|"running"|"complete"|"failed", progress, result? }

GET    /api/v1/jobs
       Returns: Job[]

Real-Time Stream

text

GET    /api/v1/stream/events
       Content-Type: text/event-stream
       Events: scan_complete | fingerprint_built | evolution_updated | error

7. Directory Structure

text

codedna/
├── cmd/
│   └── codedna/
│       └── main.py                      # CLI entry point (Typer)
│
├── analyzer/
│   ├── __init__.py
│   ├── git_parser.py                    # GitCorpusHarvester: commit traversal
│   ├── ast_extractor.py                 # ASTExtractor: tree-sitter parsing
│   ├── feature_builder.py               # FeatureVectorBuilder: vectors
│   ├── language_detector.py             # Extension → language name
│   └── supported_langs/
│       ├── __init__.py
│       ├── python_features.py           # Python-specific AST rules
│       ├── go_features.py               # Go-specific AST rules
│       ├── js_features.py               # JavaScript AST rules
│       ├── ts_features.py               # TypeScript AST rules
│       ├── rust_features.py             # Rust AST rules
│       └── java_features.py             # Java AST rules
│
├── fingerprint/
│   ├── __init__.py
│   ├── builder.py                       # FingerprintBuilder: StyleDNA assembly
│   ├── clusterer.py                     # UMAP + HDBSCAN clustering
│   ├── evolver.py                       # StyleEvolutionTracker
│   ├── comparator.py                    # Compare two StyleDNA objects
│   └── calibrator.py                    # Score calibration curves
│
├── immune_system/
│   ├── scanner/                         # Rust crate
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── main.rs                  # Binary entry point
│   │       ├── scanner.rs               # Directory + file scanner
│   │       ├── client.rs                # HTTP client for API calls
│   │       └── types.rs                 # Shared types
│   ├── scorer.py                        # StyleScorer: Mahalanobis scoring
│   ├── detector.py                      # Suspicious span localization
│   └── explainer.py                     # ExplainerEngine: feature deltas
│
├── evolution/
│   ├── __init__.py
│   ├── timeline.py                      # StyleEvolutionTracker
│   ├── shift_detector.py                # Change point detection
│   ├── era_labeler.py                   # Auto-label eras from features
│   └── report.py                        # EvolutionReport generation
│
├── integrations/
│   ├── vscode/                          # VS Code extension
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── src/
│   │       ├── extension.ts
│   │       ├── decorations.ts
│   │       ├── statusBar.ts
│   │       └── api.ts
│   ├── vim/
│   │   └── codedna.vim                  # Vim plugin
│   ├── hooks/
│   │   ├── pre_commit.sh                # Git pre-commit hook
│   │   └── prepare_commit_msg.sh        # Injects style summary into commit msg
│   └── github_action/
│       └── action.yml                   # CI/CD integration (runs locally)
│
├── api/
│   ├── server.py                        # FastAPI app definition
│   ├── middleware.py                    # CORS, local-only guard
│   ├── events.py                        # EventBus + SSE
│   └── handlers/
│       ├── scan.py
│       ├── fingerprint.py
│       ├── evolution.py
│       ├── settings.py
│       └── health.py
│
├── storage/
│   ├── db.py                            # SQLAlchemy connection + migrations
│   ├── migrations/
│   │   └── 001_initial.sql
│   ├── sample_repo.py                   # CodeSample CRUD
│   ├── vector_repo.py                   # StyleVector CRUD + bulk insert
│   ├── fingerprint_repo.py              # Fingerprint CRUD
│   ├── scan_repo.py                     # ScanResult CRUD
│   ├── evolution_repo.py                # Evolution data CRUD
│   └── settings_repo.py                 # Key/value settings store
│
├── ui/                                  # React dashboard
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── StyleMap.tsx             # UMAP cluster visualization
│   │   │   ├── ScanHistory.tsx          # Recent scans + verdicts
│   │   │   ├── EvolutionTimeline.tsx    # Feature drift charts
│   │   │   ├── FingerprintViewer.tsx    # Baseline statistics
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── StyleMapCanvas/          # D3 UMAP scatter plot
│   │   │   ├── VerdictBadge/
│   │   │   ├── FeatureDeltaCard/        # Explanation display
│   │   │   ├── FunctionScoreBar/
│   │   │   ├── DriftChart/              # Recharts time series
│   │   │   ├── ClusterLegend/
│   │   │   └── EraTimeline/
│   │   ├── hooks/
│   │   │   ├── useSSE.ts
│   │   │   ├── useFingerprint.ts
│   │   │   └── useEvolution.ts
│   │   ├── store/
│   │   │   └── codedna.ts               # Zustand store
│   │   └── api/
│   │       └── client.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── config/
│   ├── defaults.py                      # Default config values
│   ├── schema.py                        # Config schema + validation
│   └── loader.py                        # TOML loader
│
├── data/                                # Runtime data (gitignored)
│   ├── codedna.db
│   ├── fingerprints/
│   └── cache/
│
├── tests/
│   ├── unit/
│   │   ├── test_feature_builder.py
│   │   ├── test_scorer.py
│   │   ├── test_explainer.py
│   │   └── test_git_parser.py
│   ├── integration/
│   │   ├── test_scan_pipeline.py
│   │   └── test_api_endpoints.py
│   └── fixtures/
│       ├── sample_python.py
│       ├── sample_go.go
│       └── mock_dna.pkl
│
├── pyproject.toml
├── Cargo.toml                           # Workspace Cargo for Rust scanner
├── Makefile
├── Dockerfile
└── README.md

8. Configuration System
8.1 Config File (TOML)

Stored at ~/.codedna/config.toml

toml

[identity]
canonical_email = "you@example.com"
author_names = ["Your Name", "YourName"]
author_emails = [
    "you@example.com",
    "you@work.com",
    "oldname@gmail.com"
]

[corpus]
min_commits = 50                        # Minimum qualifying commits to build baseline
min_function_lines = 3
max_function_lines = 500
exclude_bulk_reformats = true
bulk_reformat_threshold = 20           # Files changed in one commit
exclude_paths = [
    "vendor/", "node_modules/", "*.min.js",
    "*.pb.go", "*_generated.*", "*.lock",
    "migrations/", "testdata/", "__pycache__/",
    ".gen.", "dist/", "build/"
]

[languages]
enabled = ["python", "go", "javascript", "typescript", "rust", "java"]
min_samples_for_baseline = 20          # Per language

[fingerprint]
clustering_enabled = true
min_cluster_size = 15
min_cluster_samples = 5
umap_n_neighbors = 15
umap_min_dist = 0.1
robust_covariance = true               # Use MinCovDet (more robust to outliers)
rebuild_on_new_commits = true
rebuild_threshold_new_commits = 25     # Rebuild fingerprint after N new commits

[scoring]
match_threshold = 75.0                 # >= 75% = MATCH
warn_threshold = 50.0                  # 50-74% = WARN
block_threshold = 30.0                 # < 30% = potential BLOCK (if enabled)
enable_blocking = false                # Default: warn only, never block
min_confidence_to_score = 0.3         # Don't score if confidence < threshold
multi_voice_scoring = true             # Score against nearest cluster, not just global mean

[hook]
enabled = true
mode = "warn"                          # "warn" | "block" | "silent"
scan_staged_only = true
max_scan_time_seconds = 5             # Abort if scan takes longer

[ide]
enable_decorations = true
decoration_threshold = 60.0           # Only decorate if match < this
status_bar_enabled = true
scan_on_save = true
debounce_ms = 800

[evolution]
track_evolution = true
bucket_size = "quarter"               # "month" | "quarter" | "year"
drift_threshold = 0.1                 # Relative change required to report drift
time_decay_enabled = false            # If true, weight recent commits more heavily
time_decay_half_life_days = 365

[storage]
db_path = "~/.codedna/codedna.db"
store_function_bodies = false          # Don't store raw code by default (privacy)
log_retention_days = 90
max_db_size_mb = 500

[api]
host = "127.0.0.1"
port = 7432
allow_external = false                 # NEVER expose beyond localhost

[ui]
open_browser_on_start = false
theme = "dark"
port = 7432

[logging]
level = "info"
file = "~/.codedna/logs/codedna.log"
max_size_mb = 50

8.2 Config Loader

Python

# config/loader.py

import tomllib
import os
from pathlib import Path
from dataclasses import dataclass, asdict


DEFAULT_CONFIG_PATH = Path.home() / ".codedna" / "config.toml"


def load(path: Path = DEFAULT_CONFIG_PATH) -> "CodeDNAConfig":
    if not path.exists():
        cfg = _default_config()
        _write_default(path, cfg)
        return cfg
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    cfg = _parse(raw)
    _validate(cfg)
    return cfg


def _default_config() -> "CodeDNAConfig":
    from config.defaults import DEFAULT_CONFIG
    return DEFAULT_CONFIG


def _write_default(path: Path, cfg):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write TOML from defaults (uses tomli_w)
    import tomli_w
    with open(path, "wb") as f:
        tomli_w.dump(asdict(cfg), f)

9. Feature Engineering Deep Dive
9.1 Feature Categories and Rationale

The feature set is organized into seven categories, each designed to capture a distinct aspect of coding style that is immune to superficial reformatting — a tool like Black or gofmt can change whitespace and line lengths, but cannot change nesting depth, early return preference, or comprehension usage.
Category	Features	Why It Matters
Naming	Name length, casing, abbreviation usage, param name patterns	Naming habits are among the most personal aspects of style
Structure	Line count, nesting depth, early returns, blank line ratio	How you decompose logic is deeply habitual
Control Flow	if/for/while ratios, ternary usage, comprehensions, match usage	Reflects paradigm preferences (imperative vs. functional)
Abstraction	Lambda density, closure usage, chaining depth, call patterns	Reveals FP vs. OOP vs. procedural tendencies
Error Handling	try/except ratio, raise patterns, assert density, Result types	Highly language-and-person-specific
Mutability	Augmented assignment ratio, global references, local var density	Reflects immutability preferences
Documentation	Comment density, docstring presence, comment length, inline ratio	Documentation habits are extremely consistent per person
9.2 Features That Are Explicitly NOT Included

To prevent false positives from formatting tools and to avoid encoding semantic meaning rather than style:

    Line length (controlled by formatters)
    Indentation width (controlled by formatters)
    Import sorting (controlled by isort, goimports)
    Trailing whitespace, semicolons
    Variable names as raw strings (too semantic, too dependent on domain)
    Any feature derived from the program's purpose or domain vocabulary

9.3 Per-Language Feature Specializations

Python

# analyzer/supported_langs/python_features.py (excerpt)

class PythonExtractor:
    """Python-specific features beyond the universal set."""

    PYTHON_SPECIFIC_FEATURES = {
        "uses_type_hints": "presence of : type and -> ReturnType annotations",
        "uses_dataclass": "presence of @dataclass decorator",
        "uses_walrus_operator": "count of := assignments",
        "uses_f_strings": "count of f-string literals vs .format() calls",
        "uses_context_managers": "count of 'with' statements",
        "uses_generators": "count of 'yield' expressions",
        "uses_slots": "presence of __slots__ = ...",
        "dunder_method_count": "number of __dunder__ methods defined",
        "uses_abstract": "presence of @abstractmethod",
        "list_vs_generator_ratio": "list comprehensions / (list comp + generator exp)",
    }

Python

# analyzer/supported_langs/go_features.py (excerpt)

class GoExtractor:
    """Go-specific features."""

    GO_SPECIFIC_FEATURES = {
        "uses_error_tuple": "count of func() (T, error) return patterns",
        "uses_defer": "count of defer statements",
        "uses_goroutine": "count of go func() invocations",
        "uses_channel": "count of <- channel operations",
        "uses_interface": "count of interface{} or any usage",
        "named_return_count": "count of named return values",
        "blank_identifier_count": "count of _ = ... assignments",
        "struct_embedding_count": "count of anonymous field embeddings",
        "early_return_on_error": "count of 'if err != nil { return' patterns",
        "uses_pointer_receiver": "method receiver is *T vs T",
    }

10. Fingerprint Modeling Deep Dive
10.1 Why Mahalanobis Distance (Not Euclidean)

Your coding style features are correlated. If you write long functions, you probably also have more control flow statements, more comments, and more local variables. Euclidean distance treats all features as independent and equally scaled — it would flag "this function is longer than average" without accounting for the fact that everything scales with length in your baseline.

Mahalanobis distance accounts for:

    Correlations between features (via the inverse covariance matrix)
    Scale differences (a feature with std=10 contributes differently from one with std=0.1)
    The shape of your personal distribution in feature space

The result: a function with 40 lines is only "anomalous" if you never write 40-line functions — not because 40 lines is universally long.
10.2 Robust Covariance Estimation (MinCovDet)

Standard covariance estimation is sensitive to outliers. If your git history includes a few monster functions from 2015, they can inflate the covariance matrix and reduce the sensitivity of your baseline. CodeDNA uses sklearn.covariance.MinCovDet with support_fraction=0.75, which finds the 75% of your samples that are most tightly clustered and fits the covariance on those, making the baseline robust to historical anomalies.
10.3 Multi-Cluster Scoring

When HDBSCAN finds multiple style clusters (e.g., "test code" vs "production code"), scoring works as follows:

text

For a new function:
  1. Compute Mahalanobis distance to global baseline centroid → d_global
  2. For each cluster:
     a. Compute Mahalanobis distance to cluster centroid → d_cluster[i]
  3. best_distance = min(d_global, min(d_cluster))
  4. match_pct = sigmoid_mapping(best_distance)

This ensures that test-style code is not flagged as "foreign" just because your production-code cluster is the dominant one.
11. Scoring & Anomaly Detection Deep Dive
11.1 One-Class vs. Closed-Set Classification

CodeDNA is fundamentally a one-class / open-set anomaly detection problem, not a multi-class classification problem. The distinction matters:
Closed-Set (authorship attribution research)	One-Class (CodeDNA's problem)
"Which of these N known authors wrote this?"	"Did you write this, or not?"
Labeled examples for all classes	Only positive ("self") examples
Standard classifier applicable	Must use one-class / anomaly detection
Well-studied	Harder: no "not-self" distribution to learn from

CodeDNA's approach: model the "self" distribution via Mahalanobis distance from a Gaussian fit to your feature vectors. Code that is far from your distribution in this space is flagged — no negative training examples needed.
11.2 Calibration

Raw Mahalanobis distances are not directly interpretable as "probability of being foreign." CodeDNA applies a calibration mapping learned from held-out "self" samples:

Python

# fingerprint/calibrator.py

import numpy as np
from sklearn.isotonic import IsotonicRegression


class ScoreCalibrator:
    """
    Maps raw Mahalanobis distances to calibrated match percentages.
    Trained on a held-out 20% split of the user's own samples.
    Self samples should score high; their distance distribution defines
    the calibration curve.
    """

    def fit(self, self_distances: np.ndarray):
        """
        self_distances: distances of held-out 'self' samples from baseline.
        We want these to map to ~80-100% match.
        """
        # Anchor points: define expected match % at known distance quantiles
        p25 = np.percentile(self_distances, 25)
        p50 = np.percentile(self_distances, 50)
        p75 = np.percentile(self_distances, 75)
        p95 = np.percentile(self_distances, 95)

        # Build calibration curve using known anchor matches
        anchor_distances = np.array([0.0, p25, p50, p75, p95, p95 * 3.0])
        anchor_matches = np.array([100.0, 92.0, 82.0, 68.0, 50.0, 20.0])

        self.calibrator = IsotonicRegression(out_of_bounds="clip", increasing=False)
        self.calibrator.fit(anchor_distances, anchor_matches)

    def transform(self, distance: float) -> float:
        return float(self.calibrator.predict([[distance]])[0])

12. Evolution & Style Drift Deep Dive
12.1 Time Decay (Optional)

By default, all historical samples contribute equally to the baseline. Optionally, with time_decay_enabled = true, more recent code is weighted more heavily — useful if you've deliberately changed your style and don't want older patterns to dilute the signal.

Python

def compute_weighted_mean(vectors: np.ndarray, timestamps: np.ndarray,
                          half_life_days: float = 365.0) -> np.ndarray:
    """Exponentially weight samples by recency."""
    now = np.max(timestamps)
    ages_days = (now - timestamps) / 86400.0
    weights = np.exp(-ages_days * np.log(2) / half_life_days)
    weights /= weights.sum()
    return np.average(vectors, axis=0, weights=weights)

12.2 Era Detection

Style eras are detected using PELT (Pruned Exact Linear Time) change-point detection on the quarterly feature mean time series. Each detected change point marks the start of a new era.

Python

# evolution/shift_detector.py

import ruptures as rpt
import numpy as np
from typing import List


class StyleShiftDetector:
    def detect_change_points(
        self,
        quarterly_values: List[float],
        penalty: float = 3.0,
    ) -> List[int]:
        """
        Returns indices (quarter offsets) where significant style shifts occurred.
        Uses the PELT algorithm (O(n) with Rbf cost).
        """
        if len(quarterly_values) < 4:
            return []
        signal = np.array(quarterly_values).reshape(-1, 1)
        algo = rpt.Pelt(model="rbf").fit(signal)
        try:
            breakpoints = algo.predict(pen=penalty)
            return [bp - 1 for bp in breakpoints[:-1]]  # Exclude final boundary
        except rpt.exceptions.BadSegmentationParameters:
            return []

13. Multi-Language Support
13.1 Language Detection

Python

# analyzer/language_detector.py

EXTENSION_MAP = {
    ".py": "python",
    ".go": "go",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".java": "java",
}

SHEBANG_MAP = {
    "python": "python",
    "python3": "python",
    "node": "javascript",
}

def detect_language(file_path: str, content: str = "") -> str | None:
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]
    # Shebang fallback
    if content.startswith("#!"):
        first_line = content.split("\n")[0]
        for key, lang in SHEBANG_MAP.items():
            if key in first_line:
                return lang
    return None

13.2 Language-Specific Minimum Samples

Some users write more Go than Python. CodeDNA tracks per-language baselines independently and reports INSUFFICIENT for languages without enough samples rather than penalizing users with mixed stacks.
Language	Min Samples for Baseline	Notes
Python	20 functions	Moderate; most Python users hit this quickly
Go	20 functions	Go functions tend to be shorter; need more
JavaScript/TypeScript	25 functions	High variability (React vs Node vs scripts)
Rust	15 functions	Rust functions tend to be distinctive
Java	20 functions	High boilerplate; need clean extraction
14. Privacy & Security Model
14.1 Privacy Principles

CodeDNA is a tool for developers, not against them. This creates a specific set of privacy commitments:
Commitment	Implementation
No code leaves the machine	All processing is local; zero network calls during operation
Function bodies not stored by default	store_function_bodies = false — only feature vectors are stored
Fingerprint not exportable without consent	Export requires explicit codedna export --confirm
No team sharing without opt-in	StyleDNA is per-user; no shared baseline by default
Audit log of all scans	Every scan result stored in SQLite with timestamp and trigger
14.2 The Stylometry Privacy Concern

Academic research has demonstrated that AST-based stylometric features can deanonymize authors with high accuracy. CodeDNA does not enable this use case by design:

    The tool only compares code against your own baseline, not a database of other developers
    There is no "identify who wrote this" API
    The scoring endpoint returns a "does this match me?" score, not "who wrote this?"
    CodeDNA never collects a centralized database of developer fingerprints

14.3 API Access Control

Python

# api/middleware.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import ipaddress


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        try:
            ip = ipaddress.ip_address(client_ip)
            if not (ip.is_loopback or ip.is_link_local):
                return Response(
                    "Access denied: CodeDNA API is localhost only.",
                    status_code=403
                )
        except ValueError:
            return Response("Invalid client address.", status_code=403)
        return await call_next(request)

15. Storage & Persistence
15.1 Database Connection

Python

# storage/db.py

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from pathlib import Path


def create_db(db_path: str):
    path = Path(db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    # WAL mode for concurrent reads during background builds
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={
            "check_same_thread": False,
            "timeout": 10,
        },
        pool_size=5,
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA cache_size=-32000")  # 32MB cache
        cursor.close()

    return engine

15.2 Vector Bulk Insert

Feature vectors are stored as serialized NumPy blobs for space efficiency:

Python

# storage/vector_repo.py

import numpy as np
import sqlite3
from typing import List


class VectorRepo:
    def bulk_insert(self, vectors: List["StyleVector"], conn: sqlite3.Connection):
        rows = []
        for v in vectors:
            blob = v.vector.astype(np.float32).tobytes()
            raw_json = __import__("json").dumps(v.raw)
            rows.append((
                __import__("uuid").uuid4().hex,
                v.function_name,
                v.file_path,
                v.language,
                v.commit_sha,
                v.timestamp_epoch,
                raw_json,
                blob,
                v.cluster_id,
            ))
        conn.executemany(
            "INSERT OR IGNORE INTO feature_vectors "
            "(id, function_name, file_path, language, commit_sha, timestamp, "
            " raw_features, vector_blob, cluster_id) VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()

    def load_matrix(self, language: str, conn: sqlite3.Connection) -> np.ndarray:
        rows = conn.execute(
            "SELECT vector_blob FROM feature_vectors WHERE language = ?", (language,)
        ).fetchall()
        if not rows:
            return np.empty((0, 0))
        arrays = [np.frombuffer(r[0], dtype=np.float32) for r in rows]
        return np.stack(arrays)

16. Logging, Observability & Debugging
16.1 Structured Logging

Python

# internal/logger.py

import structlog
import logging
from pathlib import Path


def configure_logging(level: str, log_file: str):
    log_path = Path(log_file).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(
            file=open(log_path, "a")
        ),
    )

16.2 CLI Output Format (Human-Readable)

text

🧬 CodeDNA — Immune System Report
══════════════════════════════════════════════
File:         src/auth/middleware.py
Language:     Python
Overall match: 61% ⚠️  WARN
Confidence:   0.87 (847 baseline samples)

Function-level breakdown:
  ✅ validate_token()          89% match  (lines 12–34)
  ✅ extract_claims()          84% match  (lines 36–58)
  ⚠️  handle_oauth_callback()  38% match  (lines 61–142)  ← suspicious

Top deviations in handle_oauth_callback():
  1. Function is 81 lines long. Your functions typically average 22 lines.
     (z = +2.9)
  2. Maximum nesting depth is 6. You typically nest at most 3 levels deep.
     (z = +2.4)
  3. No early returns detected. You typically use 2.1 early returns per function.
     (z = -2.1)
  4. Contains 0 comments. Your comment ratio is typically 0.18.
     (z = -1.8)
  5. Uses 4 try/except blocks. You average 0.4 per function.
     (z = +2.3)

Nearest style cluster: "production_python" (47% match)
Verdict: WARN — this code differs from your established patterns.
         Use 'codedna explain src/auth/middleware.py:61' for more detail.
══════════════════════════════════════════════

17. Testing Strategy
17.1 Test Pyramid

text

                    ┌────────────┐
                    │ E2E  (5%)  │
                    │ CLI + git  │
                    └─────┬──────┘
              ┌───────────┴──────────┐
              │   Integration (25%)  │
              │ API + DB + pipeline  │
              └───────────┬──────────┘
         ┌────────────────┴─────────────────┐
         │          Unit Tests (70%)        │
         │  Feature extraction, scoring,    │
         │  explainer, evolution tracker    │
         └──────────────────────────────────┘

17.2 Unit Tests

Python

# tests/unit/test_scorer.py

import numpy as np
import pytest
from immune_system.scorer import StyleScorer, ScoringConfig
from fingerprint.builder import StyleDNA


def make_mock_dna(n_features=50, n_samples=200) -> StyleDNA:
    """Build a mock StyleDNA where 'self' samples cluster tightly."""
    rng = np.random.default_rng(42)
    mean = rng.normal(0, 1, n_features)
    cov = np.eye(n_features) * 0.5 + rng.normal(0, 0.01, (n_features, n_features))
    cov = cov @ cov.T  # Make it positive definite
    return StyleDNA(
        owner_email="test@example.com",
        built_at=0.0,
        languages=["python"],
        clusters=[],
        global_mean={"python": mean},
        global_covariance={"python": cov},
        global_robust_cov={"python": cov},
        total_samples=n_samples,
    )


def test_self_code_scores_high():
    dna = make_mock_dna()
    scorer = StyleScorer(dna, ScoringConfig())
    # A sample drawn from the same distribution should score high
    rng = np.random.default_rng(1)
    self_vector = rng.multivariate_normal(dna.global_mean["python"],
                                          dna.global_covariance["python"])
    match_pct, confidence = scorer.score_function(self_vector, "python")
    assert match_pct >= 60.0, f"Self code scored too low: {match_pct}"


def test_foreign_code_scores_low():
    dna = make_mock_dna()
    scorer = StyleScorer(dna, ScoringConfig())
    # A wildly different sample should score low
    foreign_vector = dna.global_mean["python"] + 10.0  # Far from mean
    match_pct, confidence = scorer.score_function(foreign_vector, "python")
    assert match_pct < 40.0, f"Foreign code scored too high: {match_pct}"


def test_insufficient_language_returns_neutral():
    dna = make_mock_dna()
    scorer = StyleScorer(dna, ScoringConfig())
    vector = np.zeros(50)
    match_pct, confidence = scorer.score_function(vector, "rust")  # No Rust baseline
    assert match_pct == 50.0
    assert confidence == 0.0

Python

# tests/unit/test_feature_builder.py

from analyzer.feature_builder import FeatureVectorBuilder
from analyzer.ast_extractor import ASTFeatures


def make_mock_features(**overrides) -> ASTFeatures:
    defaults = {
        "function_name": "test_func",
        "language": "python",
        "name_length": 9,
        "name_is_snake_case": True,
        "name_is_camel_case": False,
        "name_has_abbreviation": False,
        "param_names": ["x", "y"],
        "param_name_avg_length": 1.5,
        "line_count": 15,
        "param_count": 2,
        "return_statement_count": 1,
        "early_return_count": 0,
        "max_nesting_depth": 2,
        "avg_nesting_depth": 1.2,
        "blank_line_ratio": 0.1,
        "if_count": 2, "else_count": 1, "elif_count": 0, "ternary_count": 0,
        "for_count": 1, "while_count": 0, "comprehension_count": 0, "match_case_count": 0,
        "lambda_count": 0, "closure_count": 0, "class_instantiation_count": 1,
        "function_call_count": 3, "chained_call_depth": 1,
        "try_count": 0, "except_count": 0, "finally_count": 0,
        "raise_count": 0, "assert_count": 0, "result_type_used": False,
        "assignment_count": 4, "augmented_assignment_count": 0,
        "global_var_references": 0, "local_var_count": 3,
        "comment_count": 2, "comment_line_ratio": 0.13,
        "has_docstring": True, "docstring_length": 25, "inline_comment_count": 1,
        "import_count": 3, "stdlib_import_ratio": 0.67,
        "third_party_libs": ["requests"],
    }
    defaults.update(overrides)
    return ASTFeatures(**defaults)


def test_derived_features_computed():
    builder = FeatureVectorBuilder()
    features = make_mock_features(
        early_return_count=2,
        return_statement_count=3,
    )
    sample = object()  # Minimal mock
    sample.file_path = "test.py"
    sample.language = "python"
    sample.commit_sha = "abc123"
    sample.timestamp = __import__("datetime").datetime.now()

    vector = builder.build(features, sample)
    assert "early_return_ratio" in vector.raw
    assert abs(vector.raw["early_return_ratio"] - 2 / 3) < 0.01


def test_library_encoding_deterministic():
    builder = FeatureVectorBuilder()
    libs_a = ["requests", "numpy", "pandas"]
    libs_b = ["requests", "numpy", "pandas"]
    enc_a = builder._encode_libraries(libs_a)
    enc_b = builder._encode_libraries(libs_b)
    assert (enc_a == enc_b).all()

17.3 Integration Tests

Python

# tests/integration/test_scan_pipeline.py

import pytest
import tempfile
import git
from pathlib import Path
from analyzer.git_parser import GitCorpusHarvester, HarvesterConfig
from analyzer.ast_extractor import ASTExtractor
from analyzer.feature_builder import FeatureVectorBuilder


SAMPLE_PYTHON_FUNCTION = '''
def calculate_discount(price: float, discount_pct: float) -> float:
    """Calculate the discounted price."""
    if discount_pct < 0 or discount_pct > 100:
        raise ValueError(f"Invalid discount: {discount_pct}")
    discount = price * (discount_pct / 100)
    return price - discount
'''


@pytest.fixture
def temp_repo(tmp_path):
    """Create a minimal git repo with some Python commits."""
    repo = git.Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test Author").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    src_file = tmp_path / "module.py"
    src_file.write_text(SAMPLE_PYTHON_FUNCTION * 5)  # 5 copies = 5 functions

    repo.index.add(["module.py"])
    repo.index.commit("Initial implementation")
    return repo, tmp_path


def test_harvest_extracts_functions(temp_repo):
    repo, path = temp_repo
    config = HarvesterConfig(
        author_emails=["test@example.com"],
        author_names=["Test Author"],
    )
    harvester = GitCorpusHarvester(str(path), config)
    samples = list(harvester.harvest())
    assert len(samples) > 0
    assert all(s.language == "python" for s in samples)
    assert all(s.author_email == "test@example.com" for s in samples)


def test_feature_extraction_pipeline(temp_repo):
    _, path = temp_repo
    extractor = ASTExtractor()
    builder = FeatureVectorBuilder()

    functions = extractor.extract_functions(SAMPLE_PYTHON_FUNCTION, "python")
    assert len(functions) == 1
    fn = functions[0]
    assert fn.name == "calculate_discount"

    features = extractor.extract_features(fn, "python")
    assert features.param_count == 2
    assert features.has_docstring is True
    assert features.raise_count == 1
    assert features.early_return_count == 1  # The raise before the return

17.4 Explainer Tests

Python

# tests/unit/test_explainer.py

from immune_system.explainer import ExplainerEngine
import numpy as np


def test_high_z_score_features_appear_first(mock_dna):
    explainer = ExplainerEngine(mock_dna)
    raw_features = {
        "line_count": 80.0,        # Much higher than typical 22.0
        "max_nesting_depth": 2.1,  # Close to typical 2.0
        "comment_count": 0.0,      # Much lower than typical
    }
    explanation = explainer.explain(
        raw_features=raw_features,
        vector=np.zeros(50),
        language="python",
        match_pct=35.0,
    )
    assert len(explanation.top_deltas) > 0
    # Highest z-score feature should be first
    assert abs(explanation.top_deltas[0].z_score) >= abs(explanation.top_deltas[-1].z_score)


def test_neutral_code_produces_no_deltas(mock_dna_with_known_mean):
    dna, mean_features = mock_dna_with_known_mean
    explainer = ExplainerEngine(dna)
    explanation = explainer.explain(
        raw_features=mean_features,  # Exactly average code
        vector=np.zeros(50),
        language="python",
        match_pct=95.0,
    )
    # All features near mean → no high z-scores → no deltas reported
    assert len(explanation.top_deltas) == 0

18. Build, Packaging & Installation
18.1 Makefile

Makefile

.PHONY: all build build-rust build-ui test test-unit test-integration lint clean install dev

# Full build
all: build-rust build-ui build

# Python package
build:
	pip install build
	python -m build --wheel

# Rust scanner binary
build-rust:
	cd immune_system/scanner && cargo build --release
	cp immune_system/scanner/target/release/codedna-scanner \
	   codedna/immune_system/scanner_bin

# React UI
build-ui:
	cd ui && npm ci && npm run build
	cp -r ui/dist/ codedna/api/static/

# Run all tests
test: test-unit test-integration

test-unit:
	pytest tests/unit/ -v --tb=short -x

test-integration:
	pytest tests/integration/ -v --tb=short -x --timeout=60

# Lint
lint:
	ruff check .
	mypy codedna/ --ignore-missing-imports
	cd immune_system/scanner && cargo clippy -- -D warnings

# Dev mode
dev:
	uvicorn codedna.api.server:app --reload --host 127.0.0.1 --port 7432 &
	cd ui && npm run dev

# Install git hook
install-hook:
	codedna install-hook

# Clean
clean:
	rm -rf dist/ build/ ui/dist/ .pytest_cache/ **/__pycache__/
	cd immune_system/scanner && cargo clean

# Release builds
release: all
	pyinstaller --onefile --name codedna cmd/codedna/main.py

18.2 Installation Script

Bash

#!/bin/bash
# install.sh — CodeDNA one-line installer

set -euo pipefail

CODEDNA_HOME="$HOME/.codedna"
mkdir -p "$CODEDNA_HOME/logs" "$CODEDNA_HOME/data" "$CODEDNA_HOME/cache"

echo "📦 Installing CodeDNA..."

# Check Python version
python3 -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ required'" || {
    echo "❌ Python 3.11+ required. Current: $(python3 --version)"
    exit 1
}

# Install from PyPI (or local wheel)
pip install codedna --quiet

# Install tree-sitter language bindings
python3 -c "
import subprocess
langs = ['python','go','javascript','typescript','rust','java']
for lang in langs:
    subprocess.run(['pip', 'install', f'tree-sitter-{lang}'], check=True, capture_output=True)
print('✅ Language parsers installed')
"

# Check if Rust scanner should be compiled locally
if command -v cargo &> /dev/null; then
    echo "🦀 Building Rust scanner locally..."
    codedna build-scanner
else
    echo "ℹ️  Rust not found. Using Python fallback scanner (slightly slower)."
fi

echo ""
echo "✅ CodeDNA installed successfully!"
echo ""
echo "Next steps:"
echo "  1. Run:  codedna init        (build your StyleDNA from git history)"
echo "  2. Run:  codedna start       (start the local API server)"
echo "  3. Open: http://localhost:7432 (view your style dashboard)"
echo "  4. Run:  codedna install-hook (optional: add git pre-commit hook)"
echo ""
echo "VS Code extension: search 'CodeDNA' in the Extensions marketplace"

18.3 CLI Commands (Typer)

Python

# cmd/codedna/main.py

import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(help="🧬 CodeDNA — Your Personal Style Immune System")


@app.command()
def init(
    repo: Path = typer.Argument(default=Path("."), help="Path to git repository"),
    email: Optional[str] = typer.Option(None, help="Your git author email"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Force rebuild from scratch"),
):
    """Build your StyleDNA fingerprint from git history."""
    ...


@app.command()
def scan(
    path: Path = typer.Argument(default=Path("."), help="File or directory to scan"),
    language: Optional[str] = typer.Option(None, help="Override language detection"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    verbose: bool = typer.Option(False, "-v", help="Show all functions, not just suspicious ones"),
):
    """Scan code for style anomalies."""
    ...


@app.command()
def explain(
    location: str = typer.Argument(help="File path or 'file.py:line_number'"),
):
    """Explain why a function was flagged."""
    ...


@app.command()
def evolve(
    language: str = typer.Option("python", help="Language to analyze"),
    output: Optional[Path] = typer.Option(None, "--output", help="Save report to file"),
):
    """Show your style evolution report."""
    ...


@app.command()
def start(
    port: int = typer.Option(7432, help="API server port"),
    open_browser: bool = typer.Option(False, "--open", help="Open dashboard in browser"),
):
    """Start the local CodeDNA API server and dashboard."""
    ...


@app.command()
def status():
    """Show current fingerprint status and statistics."""
    ...


@app.command()
def install_hook(
    repo: Path = typer.Argument(default=Path("."), help="Repository to install hook in"),
    mode: str = typer.Option("warn", help="Hook mode: warn | block | silent"),
):
    """Install git pre-commit hook."""
    ...


if __name__ == "__main__":
    app()

19. Platform Support Matrix
Feature	macOS (Intel)	macOS (Apple Silicon)	Linux (amd64)	Linux (arm64)	Windows (amd64)
Git corpus harvest	✅	✅	✅	✅	✅
Python AST extraction	✅	✅	✅	✅	✅
tree-sitter multi-lang	✅	✅	✅	✅	✅
Rust scanner binary	✅	✅	✅	✅	✅
UMAP + HDBSCAN	✅	✅	✅	✅	✅
SQLite persistence	✅	✅	✅	✅	✅
FastAPI local server	✅	✅	✅	✅	✅
React dashboard	✅	✅	✅	✅	✅
VS Code extension	✅	✅	✅	✅	✅
Vim plugin	✅	✅	✅	✅	⚠️ (WSL)
Git hook	✅	✅	✅	✅	⚠️ (Git Bash)
PyInstaller single binary	✅	✅	✅	✅	✅
20. Performance Targets & Benchmarks
Metric	Target	Notes
IDE scan latency (single file, 500 lines)	< 500ms P99	Incremental parse via tree-sitter
Pre-commit hook scan (staged diff)	< 2s total	Fast-path: only scan changed functions
Full corpus build (5 years, 10k commits)	< 10 minutes	Parallelized per-language
Incremental update (25 new commits)	< 60 seconds	Only re-extract changed files
UMAP fit (5,000 vectors)	< 30 seconds	One-time; cached after
HDBSCAN fit (5,000 vectors)	< 10 seconds	One-time; cached after
Mahalanobis scoring (single function)	< 5ms	NumPy vectorized
SQLite vector bulk insert (1,000 rows)	< 500ms	WAL mode enabled
Dashboard SSE event latency	< 100ms	Event → browser
Memory footprint (idle API server)	< 300MB	Baseline loaded in memory
20.1 Parallelism Budget

text

Main threads:
├── FastAPI ASGI server (uvicorn, N workers)
├── Git harvester (ThreadPoolExecutor, N_CPUS threads)
├── Feature extractor (ProcessPoolExecutor per language)
├── Fingerprint build (single thread — sklearn is not thread-safe)
├── Evolution tracker (background thread)
├── SSE broadcaster (asyncio coroutine)
└── SQLite writer (serialized — single writer)

21. Error Handling Strategy
21.1 Error Categories

Python

# codedna/errors.py

from enum import Enum


class ErrorCategory(str, Enum):
    CORPUS = "corpus"           # Git traversal, file reading errors
    EXTRACTION = "extraction"   # AST parse failures
    FINGERPRINT = "fingerprint" # Modeling, covariance errors
    SCORING = "scoring"         # Distance computation errors
    STORAGE = "storage"         # SQLite errors
    CONFIG = "config"           # Config parse/validation errors
    API = "api"                 # FastAPI handler errors


class CodeDNAError(Exception):
    def __init__(self, message: str, category: ErrorCategory, retryable: bool = False):
        super().__init__(message)
        self.category = category
        self.retryable = retryable

21.2 Scan Error Policy

Critical rule: errors during scanning MUST NOT block the user's workflow.

Python

# immune_system/scorer.py

def score_with_fallback(self, vector, language) -> tuple[float, float]:
    """
    Never raise. Return a neutral score with zero confidence on any error.
    The user's commit or IDE session must never be broken by CodeDNA failures.
    """
    try:
        return self.score_function(vector, language)
    except np.linalg.LinAlgError:
        # Singular covariance matrix — too few unique samples
        return 50.0, 0.0
    except KeyError:
        # Language not in baseline yet
        return 50.0, 0.0
    except Exception as e:
        import logging
        logging.getLogger("codedna.scorer").warning(
            "Score computation failed, returning neutral",
            exc_info=e
        )
        return 50.0, 0.0

21.3 Build Error Policy

Corpus build failures are logged per-commit and skipped, never aborted:

Python

# analyzer/git_parser.py

def _extract_functions_from_commit(self, commit):
    try:
        yield from self._do_extract(commit)
    except UnicodeDecodeError:
        self.logger.debug("Skipping binary/non-UTF8 file in commit %s", commit.hexsha[:8])
    except Exception as e:
        self.logger.warning(
            "Failed to extract from commit %s: %s — skipping",
            commit.hexsha[:8], str(e)
        )

22. Dependency Registry
22.1 Python Dependencies

toml

# pyproject.toml

[project]
name = "codedna"
version = "1.0.0"
requires-python = ">=3.11"

dependencies = [
    # Git interaction
    "GitPython>=3.1",

    # AST parsing (multi-language)
    "tree-sitter>=0.21",
    "tree-sitter-python>=0.21",
    "tree-sitter-go>=0.21",
    "tree-sitter-javascript>=0.21",
    "tree-sitter-typescript>=0.21",
    "tree-sitter-rust>=0.21",
    "tree-sitter-java>=0.21",

    # Numeric computing
    "numpy>=1.26",
    "scipy>=1.12",
    "pandas>=2.1",

    # ML: fingerprint modeling
    "scikit-learn>=1.4",
    "umap-learn>=0.5",
    "hdbscan>=0.8",

    # Change point detection (evolution)
    "ruptures>=1.1",

    # API server
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "pydantic>=2.5",

    # Storage
    "sqlalchemy>=2.0",
    "alembic>=1.13",

    # CLI
    "typer[all]>=0.9",
    "rich>=13.7",

    # Config
    "tomli>=2.0",           # Read TOML (Python < 3.11 stdlib)
    "tomli-w>=1.0",         # Write TOML

    # Structured logging
    "structlog>=24.1",

    # Utilities
    "python-uuid>=1.30",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-timeout>=2.2",
    "ruff>=0.3",
    "mypy>=1.9",
    "hypothesis>=6.99",
]

22.2 Rust Dependencies

toml

# immune_system/scanner/Cargo.toml

[package]
name = "codedna-scanner"
version = "1.0.0"
edition = "2021"

[dependencies]
# File traversal (respects .gitignore)
ignore = "0.4"

# HTTP client (calls local API)
reqwest = { version = "0.11", features = ["json"] }

# Async runtime
tokio = { version = "1", features = ["full"] }

# Serialization
serde = { version = "1", features = ["derive"] }
serde_json = "1"

# CLI argument parsing
clap = { version = "4", features = ["derive"] }

22.3 Frontend Dependencies

JSON

{
  "dependencies": {
    "react": "^18.x",
    "react-dom": "^18.x",
    "react-router-dom": "^6.x",
    "zustand": "^4.x",
    "@tanstack/react-table": "^8.x",
    "recharts": "^2.x",
    "d3": "^7.x",
    "tailwindcss": "^3.x",
    "clsx": "^2.x",
    "lucide-react": "^0.x",
    "date-fns": "^3.x",
    "axios": "^1.x"
  },
  "devDependencies": {
    "typescript": "^5.x",
    "vite": "^5.x",
    "@vitejs/plugin-react": "^4.x",
    "@types/react": "^18.x",
    "@types/d3": "^7.x",
    "vitest": "^1.x",
    "@testing-library/react": "^14.x"
  }
}

22.4 External Tools Required
Tool	Version	Required For	Install
Python	≥ 3.11	All Python code	brew install python / apt install python3
Git	Any	Repository traversal	Pre-installed on most systems
Rust + Cargo	≥ 1.75	Fast scanner binary (optional)	curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
Node.js	≥ 20	UI build	brew install node
npm	≥ 10	UI dependencies	Ships with Node.js
23. Milestone & Phased Rollout Plan
Phase 1 — Foundation (Weeks 1–4)

Goal: Working corpus harvest + feature extraction pipeline

    Set up Python project structure and pyproject.toml
    Implement GitCorpusHarvester with author identity resolution
    Implement ASTExtractor for Python only (using tree-sitter-python)
    Implement FeatureVectorBuilder with scalar + derived + library features
    SQLite schema and VectorRepo bulk insert
    Implement FingerprintBuilder (global mean + covariance, no clustering yet)
    CLI: codedna init, codedna status
    Unit tests for feature extraction + vector builder

Deliverable: codedna init on a Python repo produces a StyleDNA. codedna status shows sample count and languages.
Phase 2 — Immune System (Weeks 5–8)

Goal: Scoring, explaining, and pre-commit hook

    Implement StyleScorer (Mahalanobis distance, multi-cluster, calibration)
    Implement ExplainerEngine (z-score deltas, human-readable templates)
    Implement StyleLocalizer (per-function score breakdown in a file)
    FastAPI server: /scan/file, /scan/function, /health, /fingerprint
    Pre-commit git hook (bash)
    CLI: codedna scan, codedna explain
    Unit tests for scorer and explainer
    Integration tests for scan pipeline

Deliverable: codedna scan file.py produces a match report with plain-language explanations. Pre-commit hook warns on suspicious commits.
Phase 3 — Clustering & Multi-Language (Weeks 9–12)

Goal: Multi-voice fingerprints + additional languages

    Implement StyleClusterer (UMAP + HDBSCAN)
    Wire cluster assignments into scorer (multi-cluster scoring)
    Add Go, JavaScript, TypeScript, Rust, Java language extractors
    Per-language feature specializations (Python type hints, Go error tuples, etc.)
    Update FingerprintBuilder to emit StyleCluster objects
    Dashboard Phase 1: Style map (UMAP scatter plot), fingerprint stats
    SSE event bus
    Integration tests for multi-language pipeline

Deliverable: Users with mixed-language repos get per-language baselines. Dashboard shows cluster visualization.
Phase 4 — Evolution Tracker (Weeks 13–16)

Goal: Style timeline + drift reports

    Implement StyleEvolutionTracker (quarterly bucketing, feature drift)
    Implement StyleShiftDetector (PELT change points)
    Implement EraLabeler (auto-label eras from dominant features)
    Evolution API endpoints + SSE updates
    Dashboard Phase 2: Evolution timeline charts, era markers, feature drift sparklines
    CLI: codedna evolve
    Unit + integration tests for evolution pipeline

Deliverable: codedna evolve --language python produces a full style evolution report. Dashboard shows feature drift over time.
Phase 5 — IDE Integration & Rust Scanner (Weeks 17–20)

Goal: IDE decorations + high-performance scanning

    VS Code extension (decorations, status bar, hover explanations)
    Vim plugin (quickfix integration, :CodeDNAScan command)
    Rust scanner binary (codedna-scanner) with ignore crate
    Scanner integrated as fast-path for pre-commit and codedna scan .
    Score feedback system (codedna feedback <scan_id> false-positive)
    Dashboard Phase 3: Scan history, feedback tracking, settings UI
    Performance benchmarking + optimization pass
    75% test coverage target

Deliverable: VS Code highlights suspicious functions inline as you code. Pre-commit hook adds < 2s overhead. Rust scanner handles large repos in < 5s.
Phase 6 — Polish & v1.0 (Weeks 21–24)

Goal: Production quality, packaging, documentation

    Score calibration from feedback data
    Time-decay weighting (optional, config-gated)
    PyInstaller single-binary builds (all platforms)
    Installation script (macOS + Linux + Windows)
    Signed release artifacts
    Comprehensive README + documentation site
    End-to-end test suite
    Security review (local-only enforcement, no code exfiltration)
    v1.0 release

Deliverable: pip install codedna works out of the box. Single binary available. Full documentation published.
24. Open Questions & Future Work
24.1 Open Technical Questions
Question	Status	Notes
How many training samples are truly needed for a reliable baseline?	Open	Initial target: 50 functions per language. Needs empirical validation.
How to handle style that is deliberately foreign (e.g., you copy-paste a known-good utility and keep it as-is)?	Open	Allowlist by file path, function name, or explicit # codedna: ignore comment
Should UMAP be retrained on every fingerprint rebuild, or kept stable for consistent cluster IDs?	Open	Stable cluster IDs are better for UX; may need cluster matching across rebuilds
How to handle monorepos where different subdirectories have different style norms?	Open	Per-path sub-fingerprints; path-scoped scoring
Does calibration transfer across languages, or must each language have its own calibration curve?	Open	Likely per-language; needs empirical study
How to distinguish "foreign code" from "deliberately experimental code" (you testing a new style)?	Open	User feedback loop + time-windowed learn-from-feedback
Can the evolution tracker detect "style regression" (reverting to old habits)?	Backlog	Change-point detection on multi-dimensional feature trajectory
24.2 Potential Future Features
Feature	Description	Priority
Team mode	Shared baseline for a team; detect code that doesn't match any team member's style	High
PR-level reports	Full PR scorecard: per-author match, per-file breakdown, suitable for CI	High
GitHub Action	Run CodeDNA in CI on PRs (each developer's fingerprint synced locally)	High
CodeBERT embeddings	Optional: replace hand-engineered features with local CodeBERT embeddings for richer style capture	Medium
Refactor recommender	"This function would look more like yours if you applied these transforms"	Medium
Style exporter	Export your StyleDNA as a .json config to apply across machines	Medium
Notebook support	Analyze Jupyter notebooks (.ipynb) cell-by-cell	Low
Diff-only mode	Only scan the actual changed lines, not the full function	Medium
AI explanation mode	Optional: route explanations through a local LLM (Ollama) for richer prose	Low
24.3 Known Limitations at v1.0

    Minimum corpus requirement: Users with fewer than 50 qualifying commits per language will not get a reliable baseline. CodeDNA will report INSUFFICIENT and prompt for more data.
    New repo problem: On a brand-new codebase, there is no history to learn from. CodeDNA requires at least some history in any repo it analyzes.
    Deliberate multi-style code: If you intentionally write code in multiple distinct styles (e.g., a highly functional module and a highly procedural one), HDBSCAN should find both clusters — but only if there are enough samples of each mode (minimum min_cluster_size).
    Generated code paths: Paths that produce generated code (e.g., proto-generated files, ORM migration files) must be explicitly excluded via corpus.exclude_paths or false positives will occur.
    Language version changes: Switching from Python 2 to Python 3, or from ES5 to ES2022, will look like a major style shift in the evolution tracker — which is accurate but may generate spurious "era change" alerts unless labeled by the user.
    False positive rate without feedback: Without user feedback data, the calibration is based purely on the self-distribution. The false positive rate will improve significantly as users submit codedna feedback on flagged results.

End of CodeDNA Comprehensive Engineering Design Document — v1.0

This document is fully self-contained and sufficient to hand directly to a build agent. All AI inference is local (classical ML, no LLM required). All code samples are illustrative implementations in the correct language for each module. No data leaves the developer's machine.
