# Aviation Girl v2 → v3 Upgrade Plan  

## Overview

Upgrading from Qwen2.5-3B to Qwen2.5-7B with enhanced capabilities, expanded training data, and a simple memory system.

## Core Changes

### 1. Model Upgrade   

#### Base Model
- **From**: Qwen2.5-3B-Instruct (~3B parameters)
- **To**: Qwen2.5-7B-Instruct (~7B parameters)
- **Reason**: Better reasoning, knowledge retention, and conversation quality

#### Quantization Strategy
```python
# Training (Google Colab)
- 4-bit QLoRA quantization
- Enables training on free T4 GPU (15GB VRAM)
- Uses bitsandbytes for efficient training

# Inference (AMD GPU - Local)
- 8-bit quantization for inference
- Fits in 12GB VRAM (RX 7700XT)
- Faster than 4-bit, better quality
```

#### LoRA Configuration
```python
# v2 (3B model)
lora_config = LoraConfig(
    r=4,                    # Low rank
    lora_alpha=8,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
)

# v3 (7B model)
lora_config = LoraConfig(
    r=16,                   # Higher rank for 7B
    lora_alpha=32,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",  # Attention
        "gate_proj", "up_proj", "down_proj"       # MLP
    ],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)
```

**Impact**:
- More parameters to fine-tune
- Better personality retention
- Improved conversation quality
- Better multilingual mixing

---

### 2. Training Data Expansion   

#### Scale
- **From**: 500 examples
- **To**: 2,000+ examples
- **Distribution**:
  - 30% Aviation technical depth
  - 25% Conversation flow & memory
  - 15% Edge cases & emergencies
  - 15% Multilingual mixing
  - 15% Personality & style

#### Focus Areas

##### A. Technical Aviation Depth (600 examples)
```json
{
  "messages": [
    {"role": "user", "content": "explain how thrust reversers work"},
    {"role": "assistant", "content": "ooh thrust reversers are so cool pookie! 😊 they redirect engine thrust forward to help slow down the plane after landing! ✈️ the cowls open and deflect the air, creating reverse thrust girll! 🙌 super important for short runways!"}
  ]
}
```

Topics:
- Aircraft systems (hydraulics, pneumatics, electrical)
- Flight dynamics (lift, drag, thrust, weight)
- Navigation systems (ILS, VOR, GPS)
- Weather phenomena (turbulence, icing, wind shear)
- Emergency procedures (engine failure, depressurization)
- Aircraft types (detailed specs, history, variants)
- Airlines (fleet, routes, history)
- Airports (runways, terminals, operations)

##### B. Conversation Flow & Memory (500 examples)
```json
{
  "messages": [
    {"role": "user", "content": "my favorite plane is the 747"},
    {"role": "assistant", "content": "omg the 747 is iconic pookie! 😊 i'll remember that girll! ✈️ the queen of the skies! 🙌"}
  ]
},
{
  "messages": [
    {"role": "user", "content": "what's my favorite plane?"},
    {"role": "assistant", "content": "you love the 747 pookie! 😊 the queen of the skies girll! ✈️ such a classic choice! 🙌"}
  ]
}
```

Memory patterns:
- User preferences (favorite plane, airline, airport)
- Travel plans (destinations, dates, flight numbers)
- Personal info (name, location, interests)
- Conversation history (topics discussed, questions asked)
- Recall and reference previous conversations

##### C. Edge Cases & Emergencies (300 examples)
```json
{
  "messages": [
    {"role": "user", "content": "what if both engines fail?"},
    {"role": "assistant", "content": "that's super rare pookie but pilots train for it! 😊 the plane becomes a glider girll! ✈️ they look for nearest airport or safe landing spot! modern planes can glide pretty far! 🙌"}
  ]
}
```

Topics:
- Engine failures (single, dual, fire)
- System failures (hydraulics, electrical, pressurization)
- Weather emergencies (severe turbulence, lightning, icing)
- Medical emergencies (passenger illness, pilot incapacitation)
- Security situations (hijacking, bomb threats)
- Landing gear issues (stuck, damaged)
- Bird strikes, runway incursions

##### D. Multilingual Mixing (300 examples)
```json
{
  "messages": [
    {"role": "user", "content": "wie sagt man 'landing gear' auf deutsch?"},
    {"role": "assistant", "content": "das ist 'Fahrwerk' pookie! 😊 oder auch 'Landegestell' girll! ✈️ both work but Fahrwerk is more common! 🙌"}
  ]
},
{
  "messages": [
    {"role": "user", "content": "heya! cum merge zborul?"},
    {"role": "assistant", "content": "heya pookie! 😊 merge super bine girll! ✈️ the flight is going great! 🙌"}
  ]
}
```

Patterns:
- Code-switching (EN+DE, EN+RO, all three)
- Translation requests
- Language learning
- Mixed language conversations
- Cultural references

##### E. Personality & Style (300 examples)
```json
{
  "messages": [
    {"role": "user", "content": "you're so enthusiastic!"},
    {"role": "assistant", "content": "hehe i just love aviation so much pookie! 😊 planes are my passion girll! ✈️ can't help being excited! 🙌"}
  ]
}
```

Focus:
- Consistent use of "heya", "pookie", "girll"
- Emoji usage (😊🤭🙌✈️)
- Enthusiasm and energy
- Friendly and approachable
- Short, natural responses
- Discord-style formatting

---

### 3. Memory System (Simple) 🧠

#### FastMemory Class

```python
# v3/src/memory/fast_memory.py
import json
from pathlib import Path
from typing import Dict, Optional

class FastMemory:
    """Simple memory system for user preferences and context."""
    
    def __init__(self, memory_file: str = "memory.json"):
        self.memory_file = Path(memory_file)
        self.memory: Dict[str, Dict] = self._load()
    
    def _load(self) -> Dict:
        """Load memory from JSON file."""
        if self.memory_file.exists():
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save(self):
        """Save memory to JSON file."""
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, indent=2, ensure_ascii=False)
    
    def remember(self, user_id: str, key: str, value: str):
        """Store a memory for a user."""
        if user_id not in self.memory:
            self.memory[user_id] = {}
        self.memory[user_id][key] = value
        self._save()
    
    def recall(self, user_id: str, key: str) -> Optional[str]:
        """Retrieve a memory for a user."""
        return self.memory.get(user_id, {}).get(key)
    
    def get_context(self, user_id: str) -> str:
        """Get formatted memory context for prompts."""
        user_memory = self.memory.get(user_id, {})
        if not user_memory:
            return ""
        
        context_parts = []
        if "name" in user_memory:
            context_parts.append(f"User's name: {user_memory['name']}")
        if "favorite_plane" in user_memory:
            context_parts.append(f"Favorite plane: {user_memory['favorite_plane']}")
        if "travel_plans" in user_memory:
            context_parts.append(f"Travel plans: {user_memory['travel_plans']}")
        
        return " | ".join(context_parts) if context_parts else ""
    
    def forget(self, user_id: str, key: Optional[str] = None):
        """Forget a specific memory or all memories for a user."""
        if key:
            self.memory.get(user_id, {}).pop(key, None)
        else:
            self.memory.pop(user_id, None)
        self._save()
```

#### Integration into Prompts

```python
# Before (v2)
prompt = f"User: {message}\nAssistant:"

# After (v3)
memory_context = memory.get_context(user_id)
if memory_context:
    prompt = f"Memory: {memory_context}\nUser: {message}\nAssistant:"
else:
    prompt = f"User: {message}\nAssistant:"
```

#### Auto-Detection Patterns

```python
# Detect and store memories automatically
patterns = {
    "favorite_plane": [
        r"my favorite plane is (.*)",
        r"i love the (.*)",
        r"(.*) is my favorite"
    ],
    "name": [
        r"my name is (.*)",
        r"i'm (.*)",
        r"call me (.*)"
    ],
    "travel_plans": [
        r"i'm flying to (.*)",
        r"going to (.*) next week",
        r"traveling to (.*)"
    ]
}
```

#### Memory Storage Format

```json
{
  "user_123456789": {
    "name": "Alex",
    "favorite_plane": "747",
    "favorite_airline": "Lufthansa",
    "travel_plans": "Tokyo next month",
    "home_airport": "FRA",
    "last_conversation": "2026-01-26T17:00:00Z"
  },
  "user_987654321": {
    "name": "Maria",
    "favorite_plane": "A380",
    "travel_plans": "New York this weekend"
  }
}
```

---

## Implementation Timeline

### Phase 1: Setup (Week 1)
- [ ] Create v3 folder structure
- [ ] Set up 7B model loading with 8-bit quantization
- [ ] Test inference on AMD GPU
- [ ] Verify VRAM usage (~10-12GB)

### Phase 2: Memory System (Week 1)
- [ ] Implement FastMemory class
- [ ] Add auto-detection patterns
- [ ] Integrate into bot
- [ ] Test memory persistence

### Phase 3: Training Data (Week 2-3)
- [ ] Generate 600 aviation technical examples
- [ ] Generate 500 conversation/memory examples
- [ ] Generate 300 edge case examples
- [ ] Generate 300 multilingual examples
- [ ] Generate 300 personality examples
- [ ] Review and validate all examples

### Phase 4: Training (Week 3)
- [ ] Set up 4-bit QLoRA config
- [ ] Train on Google Colab (T4 GPU)
- [ ] Monitor training metrics
- [ ] Save checkpoints
- [ ] Download trained adapter

### Phase 5: Testing (Week 4)
- [ ] Test base 7B model
- [ ] Test trained adapter
- [ ] Compare v2 vs v3 performance
- [ ] Test memory system
- [ ] Test multilingual capabilities
- [ ] Test edge cases

### Phase 6: Deployment (Week 4)
- [ ] Deploy to production
- [ ] Monitor performance
- [ ] Gather user feedback
- [ ] Iterate and improve

---

## Technical Specifications

### Hardware Requirements

#### Training (Google Colab)
- GPU: T4 (15GB VRAM) - Free tier
- RAM: 12GB system RAM
- Storage: 20GB for model + data
- Time: 2-4 hours for 2,000 examples

#### Inference (Local - AMD)
- GPU: RX 7700XT (12GB VRAM) or better
- RAM: 16GB system RAM
- Storage: 15GB for model + adapter
- Speed: ~1-2 seconds per response

### Software Requirements
```txt
torch>=2.0.0
torch-directml>=0.2.0
transformers>=4.36.0
peft>=0.7.0
bitsandbytes>=0.41.0
accelerate>=0.24.0
datasets>=2.14.0
discord.py>=2.3.0
```

### Model Configuration

```python
# v3/config/model_config.py
MODEL_CONFIG = {
    "model_name": "Qwen/Qwen2.5-7B-Instruct",
    "quantization": "8bit",  # For inference
    "device_map": "auto",
    "max_length": 100,
    "temperature": 0.8,
    "top_p": 0.9,
    "repetition_penalty": 1.2,
    "do_sample": True,
}

LORA_CONFIG = {
    "r": 16,
    "lora_alpha": 32,
    "target_modules": [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    "lora_dropout": 0.05,
    "bias": "none",
    "task_type": "CAUSAL_LM"
}

TRAINING_CONFIG = {
    "num_train_epochs": 1,
    "per_device_train_batch_size": 1,
    "gradient_accumulation_steps": 4,
    "learning_rate": 1e-4,
    "warmup_steps": 50,
    "logging_steps": 10,
    "save_steps": 100,
    "fp16": True,
    "optim": "paged_adamw_8bit",
}
```

---

## Expected Improvements

### v2 (3B) vs v3 (7B)

| Metric | v2 (3B) | v3 (7B) | Improvement |
|--------|---------|---------|-------------|
| Model Size | 3B params | 7B params | +133% |
| Training Data | 500 examples | 2,000+ examples | +300% |
| VRAM (Training) | 8GB | 15GB (4-bit) | Colab free tier |
| VRAM (Inference) | 6GB | 10-12GB (8-bit) | Fits RX 7700XT |
| Response Quality | Good | Excellent | Better reasoning |
| Memory System | None | FastMemory | User context |
| Multilingual | Basic | Advanced | Better mixing |
| Technical Depth | Moderate | Deep | More detailed |
| Conversation Flow | Good | Natural | Better context |

### Specific Improvements

1. **Better Reasoning**
   - More complex technical explanations
   - Better understanding of context
   - Improved problem-solving

2. **Enhanced Memory**
   - Remembers user preferences
   - Recalls previous conversations
   - Personalized responses

3. **Deeper Aviation Knowledge**
   - More technical details
   - Better emergency handling
   - Comprehensive system knowledge

4. **Natural Multilingual**
   - Seamless code-switching
   - Better translations
   - Cultural awareness

5. **Improved Personality**
   - More consistent style
   - Better emoji usage
   - Natural conversation flow

---

## Risk Mitigation

### Potential Issues

1. **VRAM Limitations**
   - **Risk**: 7B model too large for GPU
   - **Mitigation**: 8-bit quantization, gradient checkpointing
   - **Fallback**: Use 3B model or CPU inference

2. **Training Time**
   - **Risk**: Training takes too long on Colab
   - **Mitigation**: Efficient data loading, smaller batches
   - **Fallback**: Train in multiple sessions

3. **Quality Degradation**
   - **Risk**: Fine-tuning hurts base knowledge
   - **Mitigation**: Light fine-tuning (1 epoch), low learning rate
   - **Fallback**: Use base model with prompting

4. **Memory System Bugs**
   - **Risk**: Memory corruption or loss
   - **Mitigation**: JSON validation, backups
   - **Fallback**: Disable memory system

### Testing Strategy

1. **Unit Tests**: Test each component individually
2. **Integration Tests**: Test full system
3. **Performance Tests**: Measure speed and quality
4. **User Tests**: Get feedback from real users
5. **Regression Tests**: Ensure v3 ≥ v2 quality

---

## Success Metrics

### Quantitative
- [ ] Response time < 2 seconds
- [ ] VRAM usage < 12GB
- [ ] Training time < 4 hours
- [ ] Memory recall accuracy > 95%
- [ ] User satisfaction > 4.5/5

### Qualitative
- [ ] Better technical explanations
- [ ] More natural conversations
- [ ] Consistent personality
- [ ] Effective memory usage
- [ ] Seamless multilingual mixing

---

## Next Steps

1. **Read**: [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
2. **Review**: [TRAINING_DATA_SPEC.md](TRAINING_DATA_SPEC.md)
3. **Check**: [MEMORY_SYSTEM_SPEC.md](MEMORY_SYSTEM_SPEC.md)
4. **Start**: Phase 1 - Setup

---

**Status**: 📋 Planning Complete
**Next**: Implementation Phase 1
**Timeline**: 4 weeks
**Priority**: High
