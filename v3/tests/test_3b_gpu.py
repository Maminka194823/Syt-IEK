"""Test the 3B model on AMD GPU."""
import sys
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from model.loader import load_base_with_adapter
from model.generator import generate_response

def test_3b_gpu():
    """Test the 3B model on AMD GPU."""
    print("=" * 50)
    print("Testing Qwen 3B Model on AMD GPU")
    print("=" * 50)
    
    base_model = "Qwen/Qwen2.5-3B-Instruct"
    adapter_path = "models/qwen_3b/checkpoints/checkpoint-145"
    
    print(f"\nLoading base model: {base_model}")
    print(f"Loading adapter from: {adapter_path}")
    print("This should be fast on GPU...\n")
    
    try:
        model, tokenizer = load_base_with_adapter(
            base_model,
            adapter_path,
            use_8bit=False
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
    print("Running Test Prompts (GPU accelerated)")
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
            print(f"⏱️ Time: {elapsed:.2f}s")
        except Exception as e:
            print(f"  Error generating response: {e}")
            return False
    
    print("\n" + "=" * 50)
    print("  All tests passed!")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = test_3b_gpu()
    sys.exit(0 if success else 1)
