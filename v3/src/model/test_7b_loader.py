"""Test loading Qwen2.5-7B with 8-bit quantization."""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

def test_7b_model():
    """Test loading Qwen2.5-7B with 8-bit quantization."""
    
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
    
    print("Configuring 8-bit quantization...")
    quantization_config = BitsAndBytesConfig(
        load_in_8bit=True,
        llm_int8_threshold=6.0,
        llm_int8_has_fp16_weight=False,
    )
    
    print("Loading model (this may take a few minutes)...")
    model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen2.5-7B-Instruct",
        quantization_config=quantization_config,
        device_map="auto",
        trust_remote_code=True,
    )
    
    print(f"Model loaded! VRAM usage: ~10-12GB")
    
    # Test inference
    messages = [
        {"role": "user", "content": "heya! what's your favorite plane?"}
    ]
    
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    print("Generating response...")
    outputs = model.generate(
        **inputs,
        max_new_tokens=100,
        temperature=0.8,
        do_sample=True,
    )
    
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"\nResponse: {response}")
    
    return True

if __name__ == "__main__":
    test_7b_model()
