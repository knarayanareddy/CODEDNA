"""Language adapter interface for CodeDNA."""
from dataclasses import dataclass
from typing import Protocol, List, Optional
from codedna.harvester.features import FeatureVector

@dataclass
class HarvesterConfig:
    store_bodies: bool = False
    max_file_bytes: int = 1048576
    language: str = "python"

class LanguageAdapter(Protocol):
    language: str
    extensions: List[str]
    def extract_features(self, source: str, config: HarvesterConfig) -> FeatureVector: ...
    def supports_incremental(self) -> bool: ...

class PythonAdapter:
    language = "python"
    extensions = [".py", ".pyw", ".pyi"]
    def extract_features(self, source: str, config: HarvesterConfig) -> FeatureVector:
        from codedna.harvester.features import extract_features
        return extract_features(source)
    def supports_incremental(self) -> bool:
        return True

_ADAPTERS = {"python": PythonAdapter()}

def get_adapter(language: str) -> Optional[LanguageAdapter]:
    return _ADAPTERS.get(language.lower())

def register_adapter(language: str, adapter: LanguageAdapter) -> None:
    _ADAPTERS[language.lower()] = adapter

def get_supported_languages() -> List[str]:
    return list(_ADAPTERS.keys())
