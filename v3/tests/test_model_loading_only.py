"""Test just the model loading part to isolate issues."""
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

def test_model_loading():
    """Test model loading step by step."""
    print("🧪 Testing Model Loading Components")
    print("=" * 50)
    
    # Step 1: Test imports
    print("Step 1: Testing imports...")
    try:
        import torch
        print("    PyTorch imported")
        
        from transformers import AutoTokenizer, AutoModelForCausalLM
        print("    Transformers imported")
        
        from peft import PeftModel
        print("    PEFT imported")
        
        from model.loader import load_base_with_adapter, get_device
        print("    Model loader imported")
        
    except Exception as e:
        print(f"    Import failed: {e}")
        return False
    
    # Step 2: Test device detection
    print("\nStep 2: Testing device detection...")
    try:
        device = get_device()
        print(f"    Device detected: {device}")
        
        has_gpu = "cuda" in str(device) or "directml" in str(device)
        print(f"  GPU available: {has_gpu}")
        
    except Exception as e:
        print(f"    Device detection failed: {e}")
        return False
    
    # Step 3: Test tokenizer loading
    print("\nStep 3: Testing tokenizer loading...")
    try:
        tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct", trust_remote_code=True)
        print("    Tokenizer loaded successfully")
        
    except Exception as e:
        print(f"    Tokenizer loading failed: {e}")
        return False
    
    # Step 4: Check model path
    print("\nStep 4: Checking model path...")
    model_path = "models/qwan_7b/aviation_girl_v3_adapter"
    
    if not Path(model_path).exists():
        # Try relative to project root
        project_root = Path(__file__).parent.parent.parent
        full_model_path = project_root / model_path
        if full_model_path.exists():
            model_path = str(full_model_path)
            print(f"    Found model at: {model_path}")
        else:
            print(f"  ⚠️ Model not found: {model_path}")
            print("  Will test base model loading only")
            model_path = None
    else:
        print(f"    Model path confirmed: {model_path}")
    
    # Step 5: Test base model loading (CPU only for safety)
    print("\nStep 5: Testing base model loading (CPU)...")
    try:
        print("  Loading base model on CPU...")
        base_model = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen2.5-7B-Instruct",
            torch_dtype=torch.float32,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )
        print("    Base model loaded successfully")
        
        # Test adapter loading if available
        if model_path:
            print("  Loading LoRA adapter...")
            model = PeftModel.from_pretrained(base_model, model_path)
            print("    Adapter loaded successfully")
        else:
            model = base_model
            print("  ⚠️ No adapter - using base model only")
        
        print("    Model loading test completed successfully!")
        
        # Quick generation test
        print("\nStep 6: Testing generation...")
        from model.generator import generate_response
        
        test_prompt = "User: heya!\nAssistant:"
        response = generate_response(
            model,
            tokenizer,
            test_prompt,
            max_new_tokens=50,
            temperature=0.8
        )
        
        print(f"  Test response: {response}")
        print("    Generation test successful!")
        
        return True
        
    except Exception as e:
        print(f"    Model loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run model loading test."""
    print("  Aviation Girl V3 - Model Loading Test")
    print("=" * 60)
    
    success = test_model_loading()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Model loading test PASSED!")
        print("  All components working correctly")
        print("  Ready for Discord bot integration")
    else:
        print("  Model loading test FAILED!")
        print("⚠️ Check the errors above")
        print("💡 Try running with smaller model or CPU-only mode")
    
    print("=" * 60)

if __name__ == "__main__":
    main()