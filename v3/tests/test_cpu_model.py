"""Test model on CPU (uses 3B for reasonable memory usage)."""
import sys
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from model.loader import load_base_with_adapter
from model.generator import generate_response

def test_cpu_model():
    """Test model on CPU with 3B (more reasonable memory usage)."""
    print("=" * 50)
    print("Testing Model on CPU")
    print("=" * 50)
    
    # Use 3B for CPU testing (7B needs ~28GB RAM on CPU)
    base_model = "Qwen/Qwen2.5-3B-Instruct"
    
    # Check if we have a 3B adapter, otherwise use 7B
    adapter_3b = Path("models/qwen_3b/checkpoints/checkpoint-145")
    adapter_7b = Path("models/qwen_7b")
    
    if adapter_3b.exists():
        adapter_path = str(adapter_3b)
        print(f"\nUsing 3B model (CPU-friendly)")
    elif adapter_7b.exists():
        print(f"\n⚠️ Only 7B adapter found - this will use ~28GB RAM!")
        print("Consider training a 3B model for CPU usage")
        base_model = "Qwen/Qwen2.5-7B-Instruct"
        adapter_path = str(adapter_7b)
    else:
        print("  No adapter found in models/qwen_3b or models/qwen_7b")
        return False
    
    print(f"Loading base model: {base_model}")
    print(f"Loading adapter from: {adapter_path}")
    print("This may take a minute...\n")
    
    try:
        model, tokenizer = load_base_with_adapter(
            base_model,
            adapter_path,
            use_8bit=False  # No quantization on CPU
        )
    except Exception as e:
        print(f"  Error loading model: {e}")
        return False
    
    # Test prompts
    test_prompts = [
        "heya! what's your favorite plane?",
        "tell me about hydraulics",
    ]
    
    print("\n" + "=" * 50)
    print("Running Test Prompts")
    print("=" * 50)
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n[Test {i}/{len(test_prompts)}]")
        print(f"User: {prompt}")
        
        full_prompt = f"User: {prompt}\nAssistant:"
        
        try:
            response = generate_response(
                model,
                tokenizer,
                full_prompt,
                max_new_tokens=100,
                temperature=0.8
            )
            print(f"Assistant: {response}")
        except Exception as e:
            print(f"  Error generating response: {e}")
            return False
    
    print("\n" + "=" * 50)
    print("  All tests passed!")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = test_cpu_model()
    sys.exit(0 if success else 1)
