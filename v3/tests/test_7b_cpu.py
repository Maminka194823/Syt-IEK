"""Test the 7B model on CPU (will be slow but should work)."""
import sys
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from model.loader import load_base_with_adapter
from model.generator import generate_response

def test_7b_cpu():
    """Test the 7B model on CPU."""
    print("=" * 50)
    print("Testing Qwen 7B Model on CPU")
    print("=" * 50)
    print("\n⚠️ This will use ~28GB RAM and be SLOW (30-60s per response)")
    print("Press Ctrl+C to cancel if needed\n")
    
    base_model = "Qwen/Qwen2.5-7B-Instruct"
    adapter_path = "models/qwan_7b/aviation_girl_v3_adapter"  # Note: typo in folder name
    
    print(f"Loading base model: {base_model}")
    print(f"Loading adapter from: {adapter_path}")
    print("This will take several minutes...\n")
    
    try:
        model = load_base_with_adapter(
            base_model,
            adapter_path,
            use_8bit=False,
            force_cpu=True  # Force CPU to avoid DirectML OOM
        )
    except Exception as e:
        print(f"  Error loading model: {e}")
        print("\nIf you ran out of memory, you need:")
        print("- At least 28GB RAM for 7B on CPU")
        print("- Or use GPU with 8-bit quantization")
        print("- Or train a 3B model instead")
        return False
    
    # Test prompts
    test_prompts = [
        "heya! what's your favorite plane?",
        "tell me about hydraulics",
    ]
    
    print("\n" + "=" * 50)
    print("Running Test Prompts (this will be slow)")
    print("=" * 50)
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n[Test {i}/{len(test_prompts)}]")
        print(f"User: {prompt}")
        print("Generating response (30-60 seconds)...")
        
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
    print("\nNote: For faster responses, use GPU or train a 3B model")
    return True

if __name__ == "__main__":
    success = test_7b_cpu()
    sys.exit(0 if success else 1)
