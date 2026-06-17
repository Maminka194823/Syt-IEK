# Start V3 Training - Quick Guide  

## What's Ready

  **High-quality training data**: 2,000+ examples in `v3/data/v3_comprehensive_training.jsonl`
  **Training notebook**: `v3/notebooks/v3_training.ipynb` 
  **All systems tested**: Memory, RAG, bot integration working
  **Hardware requirements**: Confirmed to work on Google Colab T4 (free)

## Quick Start (5 minutes)

### Step 1: Open Google Colab
1. Go to [Google Colab](https://colab.research.google.com/)
2. Upload `v3/notebooks/v3_training.ipynb`
3. Or create new notebook and copy the training code

### Step 2: Upload Training Data
```python
# In Colab, upload the training data file
from google.colab import files
uploaded = files.upload()
# Upload: v3_comprehensive_training.jsonl
```

### Step 3: Run Training
```python
# The notebook will:
# 1. Install dependencies
# 2. Load Qwen2.5-7B with 4-bit quantization
# 3. Configure LoRA for fine-tuning
# 4. Train on your data (2-4 hours)
# 5. Save adapter to Google Drive
```

### Step 4: Download Results
```python
# Download the trained adapter
files.download('aviation_girl_v3_adapter.zip')
```

### Step 5: Deploy Locally
```bash
# Extract adapter to models folder
# Update .env with model path
# Run the bot
python v3/src/bot/discord_bot_v3.py
```

## Training Configuration

```python
# Optimized for Google Colab T4 (15GB VRAM)
LORA_CONFIG = {
    "r": 16,                    # Higher rank for 7B model
    "lora_alpha": 32,
    "target_modules": [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    "lora_dropout": 0.05,
}

TRAINING_ARGS = {
    "num_train_epochs": 1,      # Light fine-tuning
    "per_device_train_batch_size": 1,
    "gradient_accumulation_steps": 4,
    "learning_rate": 1e-4,      # Conservative learning rate
    "warmup_steps": 50,
    "fp16": True,               # Memory optimization
    "optim": "paged_adamw_8bit", # 8-bit optimizer
}
```

## Expected Results

### Training Time
- **Google Colab T4**: 2-4 hours for 2,000 examples
- **Progress**: ~500 examples per hour
- **Memory usage**: ~14GB VRAM (fits in T4)

### Model Quality
- **Better technical knowledge**: Detailed aviation explanations
- **Memory integration**: Remembers user preferences
- **RAG enhancement**: Wikipedia facts with citations
- **Personality consistency**: Natural "pookie/girll" usage
- **Multilingual**: German/Romanian/Spanish mixing

### File Sizes
- **Base model**: ~13GB (Qwen2.5-7B)
- **LoRA adapter**: ~100MB (your fine-tuning)
- **Total download**: ~100MB (just the adapter)

## Troubleshooting

### "Out of Memory" Error
```python
# Reduce batch size
per_device_train_batch_size = 1
gradient_accumulation_steps = 8  # Increase this instead

# Enable gradient checkpointing
model.gradient_checkpointing_enable()
```

### "Training Too Slow"
```python
# Use smaller subset for testing
train_data = train_data[:500]  # Test with 500 examples first
```

### "Model Not Loading"
```python
# Check GPU availability
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")
```

## After Training

### Test Your Model
```bash
# Test the trained model
python v3/tests/test_7b_model.py

# Compare with v2
python v3/tests/compare_v2_v3.py
```

### Deploy to Discord
```bash
# Set up environment
cp v3/.env.example v3/.env
# Edit .env with your Discord token and model path

# Run the bot
python v3/src/bot/discord_bot_v3.py
```

## Support

If you run into issues:
1. Check the training logs for error messages
2. Verify GPU memory usage with `nvidia-smi`
3. Try reducing batch size or data size
4. Use the test scripts to validate each component

**Ready to train?** Open Google Colab and let's make Aviation Girl V3 fly! ✈️