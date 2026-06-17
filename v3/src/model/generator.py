"""Text generation utilities for V3."""
import torch

def generate_response(model, tokenizer, prompt: str, max_new_tokens: int = 150, temperature: float = 0.8):
    """Generate response from prompt.
    
    Args:
        model: The language model
        tokenizer: The tokenizer
        prompt: Input prompt
        max_new_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        
    Returns:
        Generated response text
    """
    # Tokenize input
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    # Generate
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            top_p=0.9,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.eos_token_id,
        )
    
    # Decode
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Extract only the assistant's response
    if "Assistant:" in response:
        response = response.split("Assistant:")[-1].strip()
    
    return response

def generate_chat_response(model, tokenizer, messages: list, max_new_tokens: int = 150, temperature: float = 0.8):
    """Generate response using chat template.
    
    Args:
        model: The language model
        tokenizer: The tokenizer
        messages: List of message dicts with 'role' and 'content'
        max_new_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        
    Returns:
        Generated response text
    """
    # Apply chat template
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    # Tokenize
    inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    # Generate
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            top_p=0.9,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.eos_token_id,
        )
    
    # Decode
    response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
    
    return response.strip()
