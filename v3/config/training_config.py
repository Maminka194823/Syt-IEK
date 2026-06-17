"""Training configuration for V3."""
from peft import LoraConfig
from transformers import TrainingArguments

# LoRA Configuration
LORA_CONFIG = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

# Training Arguments
TRAINING_ARGS = TrainingArguments(
    output_dir="./checkpoints",
    num_train_epochs=1,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    learning_rate=1e-4,
    warmup_steps=50,
    logging_steps=10,
    save_steps=100,
    save_total_limit=3,
    fp16=True,
    optim="paged_adamw_8bit",
    report_to="none",
)

# Model Configuration
MODEL_CONFIG = {
    "model_name": "Qwen/Qwen2.5-7B-Instruct",
    "use_4bit": True,
    "bnb_4bit_compute_dtype": "float16",
    "bnb_4bit_quant_type": "nf4",
    "use_nested_quant": False,
}

# Data Configuration
DATA_CONFIG = {
    "train_file": "../../data/v3_training_data.jsonl",
    "max_seq_length": 512,
    "packing": False,
}
