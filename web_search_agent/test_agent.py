#!/usr/bin/env python3
"""
Simple test script to test the web-search-agent logic directly.
"""
import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Force Ollama to use CPU only
os.environ['OLLAMA_GPU_LAYERS'] = '0'
os.environ['OLLAMA_NUM_GPU'] = '0'

# Import the components we need
import main
import ollama

async def test_web_search_agent(prompt: str):
    """Test the web search agent logic directly."""

    print(f"Testing web_search_agent with prompt: '{prompt}'")

    try:
        # Step 1: Use local LLM to generate search query from prompt
        print("Generating search query...")
        llm_response = ollama.chat(
            model='llama3.2',
            messages=[{'role': 'user', 'content': f'Generate a concise search query for: {prompt}'}],
            options={'num_gpu': 0}  # Force CPU only
        )
        search_query = llm_response['message']['content'].strip()
        print(f"Generated search query: '{search_query}'")

        # Step 2: Perform web search using BrowserOS
        print("Performing web search...")
        search_results = await main.perform_web_search(search_query)
        print(f"Raw search results: '{search_results}'")
        print(f"Search results length: {len(search_results)}")

        # Step 3: Synthesize response using LLM
        print("Synthesizing response...")
        synthesis_prompt = f"Based on the following search results, provide a comprehensive answer to: {prompt}\n\nSearch Results:\n{search_results}"
        final_response = ollama.chat(
            model='llama3.2',
            messages=[{'role': 'user', 'content': synthesis_prompt}],
            options={'num_gpu': 0}  # Force CPU only
        )
        response = final_response['message']['content']

        print("\n=== FINAL RESPONSE ===")
        print(response)
        print("=== END RESPONSE ===")

    except Exception as e:
        print(f"Error testing agent: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_agent.py 'your search prompt here'")
        sys.exit(1)

    prompt = sys.argv[1]
    asyncio.run(test_web_search_agent(prompt))