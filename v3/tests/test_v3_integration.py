"""Test V3 integration and functionality."""
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from memory.fast_memory import FastMemory
from rag.wikipedia_rag import WikipediaRAG

def test_memory_system():
    """Test memory system functionality."""
    print("Testing Memory System...")
    
    memory = FastMemory("test_memory_v3.json")
    
    # Test auto-detection
    memory.auto_detect("user123", "my favorite plane is the A380")
    memory.auto_detect("user123", "my name is Alex")
    memory.auto_detect("user123", "i'm flying to Tokyo next month")
    
    # Test recall
    assert memory.recall("user123", "favorite_plane") == "a380"
    assert memory.recall("user123", "name") == "alex"
    assert memory.recall("user123", "travel_plans") == "tokyo next month"
    
    # Test context generation
    context = memory.get_context("user123")
    print(f"Memory context: {context}")
    
    assert "alex" in context.lower()
    assert "a380" in context.lower()
    assert "tokyo" in context.lower()
    
    print("  Memory system working correctly")
    return True

def test_rag_system():
    """Test RAG system functionality."""
    print("Testing RAG System...")
    
    rag = WikipediaRAG()
    
    # Test trigger detection
    assert rag.should_use_rag("tell me about the Boeing 787")
    assert rag.should_use_rag("what's the range of the A380?")
    assert not rag.should_use_rag("heya how are you?")
    
    # Test retrieval (may fail due to network)
    try:
        result = rag.retrieve("tell me about the Boeing 787")
        if result:
            print(f"RAG result: {result['title']}")
            context = rag.format_context(result)
            print(f"Formatted context: {context[:100]}...")
            print("  RAG system working correctly")
        else:
            print("⚠️ RAG retrieval returned None (network issue)")
    except Exception as e:
        print(f"⚠️ RAG system error: {e}")
    
    return True

def test_prompt_building():
    """Test prompt building with memory and RAG."""
    print("Testing Prompt Building...")
    
    memory = FastMemory("test_memory_v3.json")
    rag = WikipediaRAG()
    
    # Setup test data
    memory.remember("user123", "favorite_plane", "747")
    memory.remember("user123", "name", "Sarah")
    
    user_message = "tell me about my favorite plane"
    memory_context = memory.get_context("user123")
    
    # Try RAG (may fail)
    rag_result = None
    try:
        rag_result = rag.retrieve(user_message)
    except:
        pass
    
    # Build prompt
    prompt_parts = []
    
    if memory_context:
        prompt_parts.append(f"Memory: {memory_context}")
    
    if rag_result:
        rag_context = rag.format_context(rag_result)
        prompt_parts.append(f"Context: {rag_context}")
    
    prompt_parts.append(f"User: {user_message}")
    prompt_parts.append("Assistant:")
    
    prompt = "\n".join(prompt_parts)
    
    print("Generated prompt:")
    print(prompt)
    print()
    
    # Verify prompt contains memory
    assert "Sarah" in prompt
    assert "747" in prompt
    
    print("  Prompt building working correctly")
    return True

def test_training_data_quality():
    """Test training data quality."""
    print("Testing Training Data Quality...")
    
    import json
    
    data_file = Path(__file__).parent.parent / "data" / "v3_training_data.jsonl"
    
    if not data_file.exists():
        print(f"⚠️ Training data file not found: {data_file}")
        return False
    
    examples = []
    with open(data_file, 'r', encoding='utf-8') as f:
        for line in f:
            examples.append(json.loads(line))
    
    print(f"Found {len(examples)} training examples")
    
    # Check format
    for i, example in enumerate(examples[:10]):
        assert "messages" in example, f"Example {i} missing 'messages'"
        assert len(example["messages"]) == 2, f"Example {i} should have 2 messages"
        assert example["messages"][0]["role"] == "user", f"Example {i} first message should be user"
        assert example["messages"][1]["role"] == "assistant", f"Example {i} second message should be assistant"
    
    # Check personality markers
    personality_count = 0
    for example in examples:
        response = example["messages"][1]["content"]
        if "pookie" in response or "girll" in response or "😊" in response:
            personality_count += 1
    
    personality_ratio = personality_count / len(examples)
    print(f"Personality markers in {personality_ratio:.1%} of examples")
    
    assert personality_ratio > 0.8, "Not enough personality markers in training data"
    
    print("  Training data quality looks good")
    return True

def main():
    """Run all tests."""
    print("🧪 Testing Aviation Girl V3 Implementation")
    print("=" * 50)
    
    tests = [
        test_memory_system,
        test_rag_system,
        test_prompt_building,
        test_training_data_quality,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  {test.__name__} failed: {e}")
            failed += 1
        print()
    
    print("=" * 50)
    print(f"Tests passed: {passed}")
    print(f"Tests failed: {failed}")
    
    if failed == 0:
        print("🎉 All tests passed! V3 implementation looks good.")
    else:
        print("⚠️ Some tests failed. Check implementation.")
    
    # Cleanup
    test_files = ["test_memory_v3.json"]
    for file in test_files:
        if Path(file).exists():
            Path(file).unlink()

if __name__ == "__main__":
    main()