"""Test GPU detection and performance."""
import torch
import sys

def test_gpu():
    """Test if GPU is available and working."""
    print("=" * 50)
    print("GPU Detection Test (AMD on Windows)")
    print("=" * 50)
    
    # Check for DirectML (AMD GPU on Windows)
    try:
        import torch_directml
        dml_available = True
        print("\n  DirectML (AMD GPU) is available!")
        
        # Get DirectML device
        dml_device = torch_directml.device()
        print(f"Device: {dml_device}")
        
        # Test tensor on GPU
        print("\nTesting GPU tensor operations...")
        try:
            x = torch.randn(1000, 1000).to(dml_device)
            y = torch.randn(1000, 1000).to(dml_device)
            z = torch.matmul(x, y)
            print("  GPU tensor operations work!")
            print(f"Result shape: {z.shape}")
        except Exception as e:
            print(f"  GPU tensor test failed: {e}")
            return False
            
    except ImportError:
        dml_available = False
        print("\n⚠️ DirectML not installed!")
        print("AMD GPU not available")
        print("\nTo enable AMD GPU on Windows:")
        print("1. Run: setup_amd_gpu.bat")
        print("2. Or manually: pip install torch-directml")
        
        # Check CUDA as fallback
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            print("\n  CUDA GPU detected (NVIDIA)")
            print(f"Device: {torch.cuda.get_device_name(0)}")
        else:
            print("\nRunning on CPU mode")
        
        return False
    
    print("\n" + "=" * 50)
    print("  AMD GPU is ready for AI inference!")
    print("Use: device = torch_directml.device()")
    print("=" * 50)
    return True

if __name__ == "__main__":
    success = test_gpu()
    sys.exit(0 if success else 1)
