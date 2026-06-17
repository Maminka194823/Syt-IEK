"""Model loading utilities for V3."""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

def get_device():
    """Get the best available device (DirectML for AMD, CUDA for NVIDIA, CPU fallback)."""
    try:
        import torch_directml
        return torch_directml.device()
    except ImportError:
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

def load_model_and_tokenizer(model_path: str, use_8bit: bool = True):
    """Load model and tokenizer with quantization.
    
    Args:
        model_path: Path to model or checkpoint
        use_8bit: Use 8-bit quantization
        
    Returns:
        Tuple of (model, tokenizer)
    """
    print(f"Loading tokenizer from {model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True
    )
    
    if use_8bit:
        print("Configuring 8-bit quantization...")
        quantization_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0,
            llm_int8_has_fp16_weight=False,
        )
    else:
        quantization_config = None
    
    print(f"Loading model from {model_path}...")
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=quantization_config,
        device_map="auto",
        trust_remote_code=True,
    )
    
    print("  Model loaded successfully!")
    return model, tokenizer

def load_base_with_adapter(base_model: str, adapter_path: str = None, use_8bit: bool = True, offload_to_cpu: bool = False, force_cpu: bool = False):
    """Load base model with LoRA adapter.
    
    Args:
        base_model: Base model name (e.g., "Qwen/Qwen2.5-7B-Instruct")
        adapter_path: Path to LoRA adapter
        use_8bit: Use 8-bit quantization (requires CUDA, not supported on DirectML)
        offload_to_cpu: Offload some layers to CPU to save VRAM (slower but works with large models)
        force_cpu: Force CPU-only mode (ignore GPU)
        
    Returns:
        Tuple of (model, tokenizer)
    """
    print(f"Loading base model: {base_model}...")
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    
    # Force CPU mode if requested
    if force_cpu:
        print("Loading model on CPU (forced)...")
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float32,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )
        print(f"Loading LoRA adapter from {adapter_path}...")
        model = PeftModel.from_pretrained(model, adapter_path)
        print("  Model with adapter loaded successfully!")
        print("Device: CPU")
        return model, tokenizer
    
    # Detect device
    device = get_device()
    has_cuda = torch.cuda.is_available()
    has_directml = False
    
    try:
        import torch_directml
        has_directml = True
        print(f"  Using AMD GPU via DirectML: {device}")
    except ImportError:
        pass
    
    # DirectML with CPU offloading for large models
    if has_directml and offload_to_cpu:
        print("Loading 7B model with CPU offloading (GPU + RAM hybrid)...")
        print("This uses GPU for some layers, CPU RAM for others")
        
        # Load with device_map to automatically split between GPU and CPU
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            device_map="auto",  # Automatically split between devices
            max_memory={0: "10GB", "cpu": "40GB"}  # Reserve 10GB GPU, 40GB CPU
        )
    elif has_directml:
        print("Loading model in float16 for DirectML (AMD GPU)...")
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )
        model = model.to(device)
    elif use_8bit and has_cuda:
        print("Using 8-bit quantization (NVIDIA GPU)...")
        quantization_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0,
            llm_int8_has_fp16_weight=False,
        )
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=quantization_config,
            device_map="auto",
            trust_remote_code=True,
        )
    else:
        print("Loading model on CPU (float32)...")
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float32,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )
    
    print(f"Loading LoRA adapter from {adapter_path}...")
    if adapter_path and Path(adapter_path).exists():
        model = PeftModel.from_pretrained(model, adapter_path)
    else:
        print(f"Warning: Adapter path {adapter_path} not found, using base model only")
    
    if has_directml and not offload_to_cpu:
        model = model.to(device)
    
    print("  Model with adapter loaded successfully!")
    if offload_to_cpu:
        print("⚡ Using hybrid GPU+CPU inference (some layers on GPU, some on CPU)")
    print(f"Device: {device if not offload_to_cpu else 'GPU + CPU hybrid'}")
    return model, tokenizer
