# Platform-Aware Embedding Providers

> Use Apple's on-device NLContextualEmbedding for macOS users, with automatic fallback to FastEmbed for other platforms.

## Executive Summary

Replace the current FastEmbed-only embedding provider with a platform-aware factory that:
- Uses **Apple's NLContextualEmbedding** on macOS (768D vectors, zero bundle size)
- Uses **FastEmbed** on Linux/Windows (current behavior)
- Allows explicit provider selection via config
- Maintains full API compatibility

**Duration:** 1-2 weeks  
**Risk Level:** Low (additive feature, full backward compatibility)

---

## Motivation

### Current State
- nanofolks uses FastEmbed (`bge-small`) for all embeddings
- 67 MB model size, requires download/installation
- No platform-specific optimizations

### Problems
1. **macOS users**: Download separate model despite Apple having native embeddings
2. **Bundle size**: 67 MB added to every installation
3. **Missed optimization**: Apple Silicon has native ML acceleration

### Opportunity
Apple's `NLContextualEmbedding` provides:
- **768-dimensional** vectors on macOS (vs 384 from bge-small)
- **Zero bundle size** - built into the OS
- **Privacy-first** - 100% on-device, no network calls
- **Apple Silicon optimized** - native Metal acceleration

---

## Solution Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    EmbeddingProviderFactory                     │
│                     (platform-aware)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   platform.system() == "Darwin"                                 │
│           │                                                     │
│           ├── macOS 15+ ──► AppleEmbeddingProvider (NLContext) │
│           │                                                     │
│           └── Other ──► FastEmbedProvider (current)             │
│                                                                  │
│   Or explicit: provider="apple" | provider="fastembed"          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Provider Comparison

| Aspect | Apple NLContextual | FastEmbed bge-small |
|--------|-------------------|---------------------|
| **Dimensions** | 768 (macOS) / 512 (iOS) | 384 |
| **MTEB Benchmark** | Not published | 62.2 |
| **Model Size** | 0 MB (OS bundled) | 67 MB |
| **RAM Usage** | ~50 MB | ~200-400 MB |
| **Privacy** | 100% on-device | Local (your choice) |
| **Offline** | ✅ Yes | ✅ Yes |
| **Cost** | Free (OS bundled) | Free |
| **Platforms** | macOS 14+, iOS 17+ | All |

---

## Implementation

### 1. Provider Interface

```python
# nanofolks/memory/embeddings.py

from abc import ABC, abstractmethod
from typing import List
import numpy as np

class EmbeddingProvider(ABC):
    """Abstract base for embedding providers."""
    
    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts."""
        pass
    
    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding dimensions."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier."""
        pass
```

### 2. FastEmbed Provider (Current)

```python
# nanofolks/memory/embeddings.py

class FastEmbedProvider(EmbeddingProvider):
    """FastEmbed provider using bge-small."""
    
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        from fastembed import FastEmbed
        self.model = FastEmbed(model_name=model_name)
    
    def embed(self, text: str) -> np.ndarray:
        return next(self.model.embed([text]))
    
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        return list(self.model.embed(texts))
    
    @property
    def dimensions(self) -> int:
        return 384
    
    @property
    def provider_name(self) -> str:
        return "fastembed"
```

### 3. Apple NLContextualEmbedding Provider

```python
# nanofolks/memory/embeddings.py

import platform
import json
import subprocess
from pathlib import Path

class AppleEmbeddingProvider(EmbeddingProvider):
    """Apple NLContextualEmbedding via subprocess to Swift."""
    
    def __init__(self):
        self._swift_binary = self._find_or_build_swift_binary()
        self._dimensions = 768 if platform.system() == "Darwin" else 512
    
    def _find_or_build_swift_binary(self) -> Path:
        """Locate or build the Swift embedding binary."""
        binary_path = Path(__file__).parent / "bin" / "apple-embedder"
        
        if binary_path.exists():
            return binary_path
        
        raise RuntimeError(
            "Apple embedding binary not found. "
            "Run: python -m nanofolks install apple-embeddings"
        )
    
    def embed(self, text: str) -> np.ndarray:
        result = subprocess.run(
            [str(self._swift_binary)],
            input=text,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Embedding failed: {result.stderr}")
        
        return np.array(json.loads(result.stdout))
    
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        results = []
        for text in texts:
            results.append(self.embed(text))
        return results
    
    @property
    def dimensions(self) -> int:
        return self._dimensions
    
    @property
    def provider_name(self) -> str:
        return "apple"
```

### 4. Swift Binary (apple-embedder)

```swift
// Sources/apple-embedder/main.swift

import Foundation
import NaturalLanguage

struct EmbeddingResult: Codable {
    let embedding: [Double]
}

func generateEmbedding(for text: String) -> [Double] {
    let embedding = NLEmbedding.sentenceEmbedding(for: .english)!
    let vector = embedding.vector(for: text)!
    return vector.map { Double($0) }
}

let input = readLine()!
let embedding = generateEmbedding(for: input)
let result = EmbeddingResult(embedding: embedding)

if let jsonData = try? JSONEncoder().encode(result),
   let jsonString = String(data: jsonData, encoding: .utf8) {
    print(jsonString)
}
```

### 5. Factory with Auto-Detection

```python
# nanofolks/memory/embeddings.py

import platform
from typing import Optional

class EmbeddingProviderFactory:
    """Create platform-appropriate embedding provider."""
    
    @staticmethod
    def create(provider: str = "auto") -> EmbeddingProvider:
        """
        Create an embedding provider.
        
        Args:
            provider: "auto" | "apple" | "fastembed"
                     - "auto": Detect platform, use Apple on macOS, FastEmbed elsewhere
                     - "apple": Force Apple provider (fails if unavailable)
                     - "fastembed": Force FastEmbed provider
        """
        if provider == "auto":
            return EmbeddingProviderFactory._create_auto()
        
        elif provider == "apple":
            return AppleEmbeddingProvider()
        
        elif provider == "fastembed":
            return FastEmbedProvider()
        
        else:
            raise ValueError(f"Unknown provider: {provider}. Use: auto, apple, fastembed")
    
    @staticmethod
    def _create_auto() -> EmbeddingProvider:
        """Auto-detect best provider for platform."""
        if platform.system() == "Darwin":
            try:
                return AppleEmbeddingProvider()
            except RuntimeError:
                # Apple provider not available, fall back to FastEmbed
                return FastEmbedProvider()
        else:
            return FastEmbedProvider()
    
    @staticmethod
    def is_apple_available() -> bool:
        """Check if Apple embeddings are available."""
        if platform.system() != "Darwin":
            return False
        
        try:
            AppleEmbeddingProvider()
            return True
        except RuntimeError:
            return False
```

---

## Configuration

### config.yaml

```yaml
memory:
  embedding_provider: "auto"  # "auto" | "apple" | "fastembed"
```

### Environment Variable

```bash
export NANOFOLKS_EMBEDDING_PROVIDER=apple
```

---

## Installation

### Build Swift Binary

```bash
# Build the Swift embedding binary
cd nanofolks/memory/embeddings
swift build -c release --arch arm64 --arch x86_64

# Or use the provided build script
python -m nanofolks install apple-embeddings
```

### First-Run Setup

```python
from nanofolks.memory.embeddings import EmbeddingProviderFactory

provider = EmbeddingProviderFactory.create("auto")
print(f"Using provider: {provider.provider_name}")
print(f"Embedding dimensions: {provider.dimensions}")
```

---

## Data Migration

### Embedding Dimension Handling

Since Apple uses 768D and FastEmbed uses 384D:

```python
# In memory/store.py - dimension-aware storage

class EmbeddingField:
    """Store embeddings with dimension tracking."""
    
    def __init__(self, provider: EmbeddingProvider):
        self.dimensions = provider.dimensions
        self.provider = provider.provider_name
    
    def serialize(self, embedding: np.ndarray) -> bytes:
        """Serialize embedding to bytes with header."""
        import struct
        header = struct.pack('II', self.dimensions, hash(self.provider))
        return header + embedding.astype(np.float32).tobytes()
    
    @staticmethod
    def deserialize(data: bytes) -> np.ndarray:
        import struct
        dims, _ = struct.unpack('II', data[:8])
        return np.frombuffer(data[8:], dtype=np.float32).reshape(-1, dims)
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_apple_embeddings.py

import pytest
import platform

class TestEmbeddingProviders:
    
    def test_fastembed_provider(self):
        from nanofolks.memory.embeddings import FastEmbedProvider
        
        provider = FastEmbedProvider()
        embedding = provider.embed("Hello world")
        
        assert len(embedding) == 384
        assert provider.provider_name == "fastembed"
    
    @pytest.mark.skipif(platform.system() != "Darwin", reason="Apple only")
    def test_apple_provider(self):
        from nanofolks.memory.embeddings import AppleEmbeddingProvider
        
        provider = AppleEmbeddingProvider()
        embedding = provider.embed("Hello world")
        
        assert len(embedding) == 768
        assert provider.provider_name == "apple"
    
    def test_auto_provider_detection(self):
        from nanofolks.memory.embeddings import EmbeddingProviderFactory
        
        provider = EmbeddingProviderFactory.create("auto")
        
        if platform.system() == "Darwin":
            assert provider.provider_name == "apple"
        else:
            assert provider.provider_name == "fastembed"
    
    def test_explicit_provider_override(self):
        from nanofolks.memory.embeddings import EmbeddingProviderFactory
        
        # Even on Mac, can force FastEmbed
        provider = EmbeddingProviderFactory.create("fastembed")
        assert provider.provider_name == "fastembed"
```

---

## Rollout Plan

### Phase 1: Core Implementation (Week 1)
- [ ] Implement `EmbeddingProvider` abstract base class
- [ ] Refactor `FastEmbedProvider` to use new interface
- [ ] Implement `AppleEmbeddingProvider` with subprocess bridge
- [ ] Create Swift binary and build script
- [ ] Implement `EmbeddingProviderFactory` with auto-detection

### Phase 2: Integration (Week 1-2)
- [ ] Update memory/store.py to use factory
- [ ] Add config option for provider selection
- [ ] Handle dimension differences in storage
- [ ] Add environment variable support

### Phase 3: Testing & Polish (Week 2)
- [ ] Unit tests for all providers
- [ ] Integration tests with memory system
- [ ] Performance benchmarks (Apple vs FastEmbed)
- [ ] Documentation update

---

## Alternative Approaches

### Option 1: PyObjC Direct (No Subprocess)
```python
# Use PyObjC to call NLContextualEmbedding directly
from Foundation import NLEmbedding

embedding = NLEmbedding.sentenceEmbedding(for: .english)
vector = embedding.vector(for: text)
```
**Pros:** No subprocess overhead  
**Cons:** More complex Python/Swift interop

### Option 2: MLX (Apple's Python ML Framework)
```python
# pip install mlx
import mlx.core as mx
# Use MLX's embedding capabilities
```
**Pros:** Official Apple ML path, best performance  
**Cons:** Limited model support currently

### Option 3: CoreML Export
Export bge-small to CoreML, run locally
**Pros:** Benchmark-known quality  
**Cons:** Significant setup work

**Recommendation:** Start with subprocess (simplest), migrate to PyObjC if needed.

---

## Open Questions

1. **Quality Assurance**: How do we validate Apple embeddings meet our quality bar?
   - Proposal: Run eval on existing test cases, compare recall@k

2. **Dimension Migration**: Existing installations have 384D embeddings
   - Proposal: Keep both, re-embed on access if dimensions mismatch

3. **macOS Version Detection**: NLContextualEmbedding requires macOS 14+
   - Proposal: Check `platform.mac_ver()` and fall back gracefully

4. **Future Apple Silicon**: What about iOS/iPadOS support?
   - Proposal: Future work - would need platform check expansion

---

## References

- [Apple NLContextualEmbedding Documentation](https://developer.apple.com/documentation/naturallanguage/nlcontextualembedding)
- [NaturalLanguageEmbeddings Swift Package](https://github.com/buh/NaturalLanguageEmbeddings)
- [WWDC 2025: Foundation Models Framework](https://developer.apple.com/videos/play/wwdc2025/286/)
- [FastEmbed Documentation](https://github.com/AnswerDotAI/fastembed)
