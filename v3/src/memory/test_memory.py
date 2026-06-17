"""Test memory system."""
from fast_memory import FastMemory

def test_memory():
    """Test memory system."""
    memory = FastMemory("test_memory.json")
    
    # Test manual storage
    print("Test 1: Manual storage")
    memory.remember("user123", "favorite_plane", "747")
    assert memory.recall("user123", "favorite_plane") == "747"
    print("✓ Manual storage works")
    
    # Test auto-detection
    print("\nTest 2: Auto-detection")
    memory.auto_detect("user123", "my name is Alex")
    assert memory.recall("user123", "name") == "alex"
    print("✓ Auto-detection works")
    
    # Test context generation
    print("\nTest 3: Context generation")
    memory.remember("user123", "travel_plans", "Tokyo next month")
    context = memory.get_context("user123")
    print(f"Context: {context}")
    assert "747" in context
    assert "Alex" in context or "alex" in context
    print("✓ Context generation works")
    
    # Test forgetting
    print("\nTest 4: Forgetting")
    memory.forget("user123", "name")
    assert memory.recall("user123", "name") is None
    print("✓ Forgetting works")
    
    print("\n  All tests passed!")

if __name__ == "__main__":
    test_memory()
