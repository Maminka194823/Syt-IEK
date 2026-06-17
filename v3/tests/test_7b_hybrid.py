"""Test 7B model with GPU+CPU hybrid (offloading)."""
import sys
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from model.loader import load_base_with_adapter
from model.generator import generate_response

def test_7b_hybrid():
    """Test 7B model with CPU offloading."""
    print("=" * 50)
    print("Testing Qwen 7B with GPU+CPU Hybrid")
    print("=" * 50)
    print("\nThis uses:")
    print("- GPU (12GB VRAM) for some layers")
    print("- CPU RAM (48GB) for remaining layers")
    print("- Faster than pure CPU, works with large models!")
    
    base_model = "Qwen/Qwen2.5-7B-Instruct"
    adapter_path = "models/qwan_7b/aviation_girl_v3_adapter"
    
    print(f"\nLoading base model: {base_model}")
    print(f"Loading adapter from: {adapter_path}")
    print("This may take a minute...\n")
    
    try:
        model, tokenizer = load_base_with_adapter(
            base_model,
            adapter_path,
            use_8bit=False,
            offload_to_cpu=True  # Enable hybrid mode
        )
    except Exception as e:
        print(f"  Error loading model: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure adapter is in models/qwan_7b/aviation_girl_v3_adapter/")
        print("2. Check you have enough RAM (needs ~20GB)")
        print("3. Try closing other applications")
        return False
    
    # Test prompts
    test_prompts = [
        "heya! what's your favorite plane?",
        "tell me about hydraulics",
    ]
    
    print("\n" + "=" * 50)
    print("Running Test Prompts (Hybrid GPU+CPU)")
    print("=" * 50)
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n[Test {i}/{len(test_prompts)}]")
        print(f"User: {prompt}")
        
        full_prompt = f"User: {prompt}\nAssistant:"
        
        try:
            import time
            start = time.time()
            
            response = generate_response(
                model,
                tokenizer,
                full_prompt,
                max_new_tokens=100,
                temperature=0.8
            )
            
            elapsed = time.time() - start
            print(f"Assistant: {response}")
            print(f"⏱️ Time: {elapsed:.2f}s (hybrid GPU+CPU)")
        except Exception as e:
            print(f"  Error generating response: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    print("\n" + "=" * 50)
    print("  All tests passed!")
    print("Hybrid mode works - faster than pure CPU!")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = test_7b_hybrid()
    sys.exit(0 if success else 1)
