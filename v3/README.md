# Aviation Girl v3  7B Upgrade 

Major upgrade from 3B to 7B model with expanded training data and memory system.

## What's New in V3

###  Model Upgrade
- **Qwen2.5-3B** → **Qwen2.5-7B-Instruct**
- 133% more parameters (3B → 7B)
- Better reasoning and conversation quality
- 8-bit quantization for inference (fits in 12GB VRAM)
- 4-bit QLoRA for training (free Colab T4 GPU)

###  Training Data Expansion
- **500 examples** → **2,000+ examples** (4x increase)
- 30% Aviation technical depth
- 25% Conversation flow & memory
- 15% Edge cases & emergencies
- 15% Multilingual mixing (EN+DE+RO)
- 15% Personality & style

###  Memory System
- Simple FastMemory class (~50 lines)
- Auto-detects user preferences
- Stores: name, favorite plane, travel plans, etc.
- Persistent JSON storage
- Integrated into prompts

###  RAG System
- Wikipedia API integration
- Automatic query detection
- Real-time knowledge retrieval
- Source citations
- Fast caching (< 500ms)

## Quick Start

### 1. Read Documentation
- [V2 vs V3 Comparison](docs/V2_VS_V3_COMPARISON.md) - See the differences!
- [V3 Upgrade Plan](docs/implementation/V3_UPGRADE_PLAN.md) - Complete overview
- [Implementation Guide](docs/implementation/IMPLEMENTATION_GUIDE.md) - Step-by-step
- [Training Data Spec](docs/implementation/TRAINING_DATA_SPEC.md) - Data generation
- [Memory System Spec](docs/implementation/MEMORY_SYSTEM_SPEC.md) - Memory details
- [RAG System Spec](docs/implementation/RAG_SYSTEM_SPEC.md) - RAG details

### 2. Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Test 7B model loading
python src/model/test_7b_loader.py
```

### 3. Implement Memory & RAG Systems
```bash
# Implement FastMemory class
# See: docs/implementation/MEMORY_SYSTEM_SPEC.md

# Implement WikipediaRAG class
# See: docs/implementation/RAG_SYSTEM_SPEC.md
```

### 4. Generate Training Data
```bash
# Generate 2,000+ examples
# See: docs/implementation/TRAINING_DATA_SPEC.md
```

### 5. Train on Colab
```bash
# Open notebooks/v3_training.ipynb in Google Colab
# Upload training data
# Train with 4-bit QLoRA (~2-4 hours)
```

### 6. Deploy
```bash
# Load trained adapter
# Run bot with memory system
```

## Project Structure

```
v3/
├── README.md                    # This file
├── docs/
│   ├── V2_VS_V3_COMPARISON.md  # V2 vs V3 comparison
│   └── implementation/          # Implementation docs
│       ├── README.md
│       ├── V3_UPGRADE_PLAN.md
│       ├── IMPLEMENTATION_GUIDE.md
│       ├── TRAINING_DATA_SPEC.md
│       ├── MEMORY_SYSTEM_SPEC.md
│       └── RAG_SYSTEM_SPEC.md
├── src/
│   ├── bot/                    # Discord bot (v3)
│   ├── model/                  # Model loading (7B)
│   ├── memory/                 # FastMemory system
│   ├── rag/                    # WikipediaRAG system
│   └── training/               # Data generation
├── config/                     # Configuration files
├── data/                       # Training data (2,000+ examples)
└── notebooks/                  # Colab training notebooks
```

## Core Changes

### 1. Model Configuration

```python
# v2 (3B)
MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"
LORA_R = 4
TARGET_MODULES = ["q_proj", "v_proj"]

# v3 (7B)
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
LORA_R = 16
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj"
]
```

### 2. Training Data

```python
# v2
TRAINING_EXAMPLES = 500

# v3
TRAINING_EXAMPLES = 2000+
CATEGORIES = {
    "aviation_technical": 600,
    "conversation_memory": 500,
    "edge_cases": 300,
    "multilingual": 300,
    "personality": 300
}
```

### 3. Memory System

```python
# v2
# No memory system

# v3
from memory.fast_memory import FastMemory

memory = FastMemory("user_memory.json")
memory.auto_detect(user_id, message)
context = memory.get_context(user_id)
prompt = f"Memory: {context}\nUser: {message}\nAssistant:"
```

### 4. RAG System

```python
# v2
# No RAG system

# v3
from rag.wikipedia_rag import WikipediaRAG

rag = WikipediaRAG()
result = rag.retrieve("Tell me about the Boeing 787")
rag_context = rag.format_context(result)
prompt = f"Context: {rag_context}\nUser: {message}\nAssistant:"
```

## Expected Improvements

| Metric | v2 (3B) | v3 (7B) | Improvement |
|--------|---------|---------|-------------|
| Parameters | 3B | 7B | +133% |
| Training Data | 500 | 2,000+ | +300% |
| Response Quality | Good | Excellent | Better reasoning |
| Technical Depth | Moderate | Deep | More detailed |
| Memory | None | FastMemory | User context |
| RAG | None | Wikipedia | Real-time knowledge |
| Multilingual | Basic | Advanced | Better mixing |

## Hardware Requirements

### Training (Google Colab)
- GPU: T4 (15GB VRAM) - **Free tier**
- RAM: 12GB system RAM
- Time: 2-4 hours
- Cost: **Free**

### Inference (Local - AMD)
- GPU: RX 7700XT (12GB VRAM) or better
- RAM: 16GB system RAM
- VRAM: 10-12GB (8-bit quantization)
- Speed: 1-2 seconds per response

## Implementation Timeline

- **Week 1**: Setup & Memory System
- **Week 2-3**: Training Data Generation
- **Week 3**: Training on Colab
- **Week 4**: Testing & Deployment

## Documentation

### Comparison
- [V2 vs V3 Comparison](docs/V2_VS_V3_COMPARISON.md) - Side-by-side comparison with examples

### Implementation Docs
- [V3 Upgrade Plan](docs/implementation/V3_UPGRADE_PLAN.md) - Complete plan
- [Implementation Guide](docs/implementation/IMPLEMENTATION_GUIDE.md) - Step-by-step
- [Training Data Spec](docs/implementation/TRAINING_DATA_SPEC.md) - Data details
- [Memory System Spec](docs/implementation/MEMORY_SYSTEM_SPEC.md) - Memory system
- [RAG System Spec](docs/implementation/RAG_SYSTEM_SPEC.md) - RAG system

### Main Project Docs
- [Main README](../README.md) - Project overview
- [Documentation Index](../docs/README.md) - All documentation
- [Quick Start](../docs/setup/QUICK_START.md) - Get started

## Status

- [x] Planning complete
- [x] Documentation written
- [x] V2 vs V3 comparison created
- [x] Setup & testing 
- [x] Memory system implementation 
- [x] RAG system implementation 
- [x] Bot integration 
- [x] Training scripts 
- [ ] Training data generation (ready to run)
- [ ] Training on Colab (ready to train)
- [ ] Testing & validation
- [ ] Deployment


