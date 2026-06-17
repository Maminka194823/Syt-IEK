"""Test the trained 7B model."""
import sys
from pathlib import Path

# Add parent directories to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from model.loader import load_base_with_adapter
from model.generator import generate_response

def test_7b_model():
    """Test the 7B model with adapter."""
    print("=" * 50)
    print("Testing Qwen 7B Model")
    print("=" * 50)
    
    # Load model
    base_model = "Qwen/Qwen2.5-7B-Instruct"
    adapter_path = "models/qwen_7b"
    
    print(f"\nLoading base model: {base_model}")
    print(f"Loading adapter from: {adapter_path}")
    print("This may take a minute...\n")
    
    try:
        model, tokenizer = load_base_with_adapter(
            base_model,
            adapter_path,
            use_8bit=True
        )
    except Exception as e:
        print(f"  Error loading model: {e}")
        print("\nMake sure:")
        print("1. The adapter is in models/qwen_7b/")
        print("2. You have enough RAM/VRAM")
        print("3. PyTorch and transformers are installed")
        return False
    
    # Test prompts
    test_prompts = [
        "heya! what's your favorite plane?",
        "tell me about hydraulics",
        "what's the difference between turbofan and turbojet?",
        "how does a jet engine work?",
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
                max_new_tokens=150,
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
    success = test_7b_model()
    sys.exit(0 if success else 1)
