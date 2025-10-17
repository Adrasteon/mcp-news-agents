import asyncio
import logging
import os
import subprocess
import time
import signal
import atexit
import psutil
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright
from .browseros_client import BrowserOSClient
import json
from typing import List
from .executor import validate_plan, execute_plan

# Force Ollama to use CPU only to prevent GPU memory issues
os.environ['OLLAMA_GPU_LAYERS'] = '0'
os.environ['OLLAMA_NUM_GPU'] = '0'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSearchInput(BaseModel):
    prompt: str = Field(..., description="Natural language prompt for web search and information retrieval")

class WebSearchOutput(BaseModel):
    response: str = Field(..., description="Synthesized information from web search")

# Global state for resource management
_browseros_process: Optional[subprocess.Popen] = None
_active_connections = 0
_max_concurrent_connections = 3  # Limit concurrent browser connections
_connection_semaphore = asyncio.Semaphore(_max_concurrent_connections)

def cleanup_browseros():
    """Clean up BrowserOS process and resources."""
    global _browseros_process
    if _browseros_process:
        logger.info("Cleaning up BrowserOS process...")
        try:
            # Try graceful shutdown first
            if _browseros_process.poll() is None:
                # Send SIGTERM first
                _browseros_process.terminate()
                try:
                    _browseros_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't respond
                    logger.warning("BrowserOS didn't respond to SIGTERM, force killing...")
                    _browseros_process.kill()
                    _browseros_process.wait()
            logger.info("BrowserOS process cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up BrowserOS: {e}")
        finally:
            _browseros_process = None

def get_memory_usage():
    """Get current memory usage of BrowserOS process."""
    global _browseros_process
    if _browseros_process and _browseros_process.poll() is None:
        try:
            process = psutil.Process(_browseros_process.pid)
            memory_mb = process.memory_info().rss / 1024 / 1024
            return memory_mb
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return 0
        except Exception as e:
            logger.warning(f"Error getting memory usage: {e}")
            return 0
    return 0

def check_gpu_resources():
    """Check GPU memory availability before LLM operations."""
    try:
        # Check NVIDIA GPU memory if available
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                used, total = line.split(',')
                used_mb = int(used.strip())
                total_mb = int(total.strip())
                available_mb = total_mb - used_mb

                # Reserve at least 2GB for GPU operations
                if available_mb < 2048:
                    logger.warning(f"Low GPU memory: {available_mb}MB available, {used_mb}MB used")
                    return False

        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        # If nvidia-smi not available, assume CPU-only or no GPU check needed
        logger.info("GPU monitoring not available, assuming CPU-only operation")
        return True
    except Exception as e:
        logger.error(f"Error checking GPU resources: {e}")
        return False

def get_ollama_client():
    """Safely import and return ollama client with resource checks."""
    try:
        # Check resources before importing ollama
        if not check_gpu_resources():
            raise RuntimeError("Insufficient GPU resources for LLM operations")

        # Lazy import ollama
        import ollama
        return ollama
    except ImportError as e:
        raise RuntimeError(f"Failed to import ollama: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to initialize ollama client: {e}")

def check_system_resources():
    """Check if system has enough resources for new operations."""
    try:
        memory = psutil.virtual_memory()
        available_memory_gb = memory.available / 1024 / 1024 / 1024

        # Reserve at least 2GB for system
        if available_memory_gb < 2.0:
            logger.warning(f"Low memory: {available_memory_gb:.1f}GB available")
            return False

        # Check BrowserOS memory usage
        browseros_memory = get_memory_usage()
        if browseros_memory > 2000:  # 2GB limit
            logger.warning(f"BrowserOS using too much memory: {browseros_memory:.1f}MB")
            return False

        return True
    except Exception as e:
        logger.error(f"Error checking system resources: {e}")
        # Don't fail on resource check errors, just log and continue
        return True

# Initialize FastMCP app
app = FastMCP(
    name="web_search_agent",
    version="1.0.0"
)

def ensure_browseros_running():
    """Ensure BrowserOS is running with CDP enabled."""
    global _browseros_process

    appimage_path = os.path.join(os.path.dirname(__file__), "BrowserOS.AppImage")

    if not os.path.exists(appimage_path):
        logger.error(f"BrowserOS AppImage not found at {appimage_path}")
        return False

    # Check system resources first (but don't fail if check fails)
    try:
        if not check_system_resources():
            logger.warning("System resource check failed, but continuing anyway...")
    except Exception as e:
        logger.warning(f"Resource check failed: {e}, continuing anyway...")

    # Check if BrowserOS is already running (simple check for CDP port)
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 9222))
        sock.close()
        if result == 0:
            # Verify the process is still our tracked process
            if _browseros_process and _browseros_process.poll() is None:
                logger.info("BrowserOS is already running")
                return True
            else:
                # Port is open but our process is gone - clean up and restart
                logger.warning("BrowserOS port open but process not tracked, cleaning up...")
                cleanup_browseros()
    except Exception as e:
        logger.error(f"Error checking BrowserOS status: {e}")

    # Clean up any existing process
    cleanup_browseros()

    # Start BrowserOS
    try:
        logger.info("Starting BrowserOS...")
        cmd = [
            appimage_path,
            "--remote-debugging-port=9222",
            "--no-first-run",
            "--no-sandbox",  # Required on Ubuntu for AppImage
            "--user-data-dir=/tmp/browseros-data",  # Isolated profile
            "--disable-dev-shm-usage",  # Use disk for shared memory
        ]

        # Start in background
        _browseros_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )

        # Wait for CDP to be available
        for i in range(30):  # Wait up to 30 seconds
            time.sleep(1)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('127.0.0.1', 9222))
                sock.close()
                if result == 0:
                    logger.info("BrowserOS started successfully")
                    return True
            except:
                pass

        logger.error("BrowserOS failed to start within timeout")
        cleanup_browseros()
        return False

    except Exception as e:
        logger.error(f"Failed to start BrowserOS: {e}")
        cleanup_browseros()
        return False

async def perform_web_search(search_query: str) -> str:
    """Perform web search using BrowserOS via Playwright CDP connection."""
    global _active_connections

    # Check system resources (but don't fail if check fails)
    try:
        if not check_system_resources():
            logger.warning("System resource check failed, but continuing anyway...")
    except Exception as e:
        logger.warning(f"Resource check failed: {e}, continuing anyway...")

    # Limit concurrent connections
    async with _connection_semaphore:
        _active_connections += 1
        try:
            # Ensure BrowserOS is running
            if not ensure_browseros_running():
                return "Error: Could not start BrowserOS. Please ensure BrowserOS.AppImage is present and executable."

            # Connect to BrowserOS CDP with timeout
            cdp_url = "http://127.0.0.1:9222"  # BrowserOS CDP endpoint

            async with async_playwright() as p:
                try:
                    # Connect with timeout
                    browser = await asyncio.wait_for(
                        p.chromium.connect_over_cdp(cdp_url),
                        timeout=10.0
                    )

                    try:
                        # Get or create context
                        context = browser.contexts[0] if browser.contexts else await browser.new_context()

                        # Create new page for this search
                        page = await context.new_page()

                        try:
                            # Set reasonable timeouts
                            page.set_default_timeout(30000)  # 30 seconds
                            page.set_default_navigation_timeout(30000)

                            # Navigate to DuckDuckGo
                            await page.goto("https://duckduckgo.com", wait_until="domcontentloaded")

                            # Enter search query
                            await page.fill("input[name='q']", search_query)
                            await page.press("input[name='q']", "Enter")

                            # Wait for results with timeout
                            await asyncio.wait_for(
                                page.wait_for_load_state("networkidle"),
                                timeout=15.0
                            )

                            # Extract search results from DuckDuckGo
                            results = await page.query_selector_all("h2 a")
                            search_results = []
                            for i, result in enumerate(results[:10]):  # Check more results
                                try:
                                    title = await result.inner_text()
                                    href = await result.get_attribute("href")
                                    # Skip DuckDuckGo internal links and empty results
                                    if href and href.startswith("http") and not href.startswith("https://duckduckgo.com"):
                                        search_results.append(f"{len(search_results)+1}. {title} - {href}")
                                        if len(search_results) >= 5:  # Stop at 5 real results
                                            break
                                except Exception as e:
                                    logger.warning(f"Error extracting result {i}: {e}")
                                    continue

                            return "\n".join(search_results) if search_results else "No search results found."

                        finally:
                            # Always close the page
                            try:
                                await page.close()
                            except Exception as e:
                                logger.warning(f"Error closing page: {e}")

                    finally:
                        # Always close the browser connection
                        try:
                            await browser.close()
                        except Exception as e:
                            logger.warning(f"Error closing browser: {e}")

                except asyncio.TimeoutError:
                    logger.error("Timeout connecting to BrowserOS")
                    return "Error: Timeout connecting to browser."
                except Exception as e:
                    logger.error(f"Error connecting to BrowserOS: {e}")
                    return f"Error: Could not connect to BrowserOS. Make sure BrowserOS is running with CDP enabled. {e}"

        finally:
            _active_connections -= 1

            # Periodic cleanup check
            if _active_connections == 0:
                memory_usage = get_memory_usage()
                if memory_usage > 1500:  # If over 1.5GB, consider cleanup
                    logger.info(f"BrowserOS memory usage high ({memory_usage:.1f}MB), considering restart...")
                    # Don't auto-restart, just log for now

def web_search_info(input: WebSearchInput) -> WebSearchOutput:
    """Search the web and retrieve relevant information."""
    try:
        # Check system resources before starting (but don't fail)
        try:
            if not check_system_resources():
                logger.warning("System resource check failed, but continuing anyway...")
        except Exception as e:
            logger.warning(f"Resource check failed: {e}, continuing anyway...")

        # Get ollama client with resource checks
        ollama = get_ollama_client()

        # Use local LLM to generate a JSON action plan for BrowserOS MCP
        logger.info(f"Processing prompt: {input.prompt}")

        plan_prompt = (
            "You are an assistant that outputs a JSON array of browser actions to perform. "
            "Do NOT output any additional text. Only return valid JSON.\n"
            "Allowed actions: goto, wait, click, fill, press, extract, extract_list, eval_js, screenshot.\n"
            "Each action should be an object with at least the 'action' field and either 'value' or 'selector' as appropriate.\n"
            "Limit plan length to 12 actions.\n"
            f"Task: produce an action plan to find authoritative information and extract key content to answer: {input.prompt}\n"
            "Prefer extracting article title and body. Use extract_list to collect candidate links.\n"
        )

        llm_response = ollama.chat(
            model='llama3.2',
            messages=[{'role': 'user', 'content': plan_prompt}],
            options={'timeout': 45, 'num_gpu': 0}
        )

        plan_text = llm_response['message']['content'].strip()
        logger.info(f"LLM returned plan text: {plan_text[:200]}")

        # Try to parse JSON plan; if parsing fails, fall back to the old search-query approach
        action_plan = None
        try:
            action_plan = json.loads(plan_text)
            if not isinstance(action_plan, list):
                logger.warning("LLM plan parsed but is not a list; falling back to search query flow")
                action_plan = None
        except Exception as e:
            logger.warning(f"Failed to parse JSON plan from LLM: {e}; falling back to search query flow")

        search_results = ""
        # Use BrowserOS MCP plan executor if we have a valid plan
        if action_plan:
            try:
                client = BrowserOSClient(use_klavis=False)  # prefer direct local MCP by default
                # Execute plan step-by-step so we can validate and recover per-action
                validated = validate_plan(action_plan)
                exec_result = execute_plan(validated, client)
                # Convert output into text for synthesis
                try:
                    search_results = json.dumps(exec_result, indent=2)
                except Exception:
                    search_results = str(exec_result)
            except Exception as e:
                logger.warning(f"BrowserOS MCP plan execution failed: {e}; falling back to CDP search: {e}")
                # Fallback to old flow
                try:
                    # Generate a concise query via LLM (old behavior)
                    llm_response = ollama.chat(
                        model='llama3.2',
                        messages=[{'role': 'user', 'content': f'Generate a concise search query for: {input.prompt}'}],
                        options={'timeout': 30, 'num_gpu': 0}
                    )
                    search_query = llm_response['message']['content'].strip()
                    logger.info(f"Fallback generated search query: {search_query}")
                    search_results = asyncio.run(perform_web_search(search_query))
                except Exception as e2:
                    logger.error(f"Fallback search failed: {e2}")
                    return WebSearchOutput(response=f"Error executing plan and fallback search failed: {e2}")

        else:
            # No valid plan: generate search query and use CDP flow
            try:
                llm_response = ollama.chat(
                    model='llama3.2',
                    messages=[{'role': 'user', 'content': f'Generate a concise search query for: {input.prompt}'}],
                    options={'timeout': 30, 'num_gpu': 0}  # Force CPU only
                )
                search_query = llm_response['message']['content'].strip()
                logger.info(f"Generated search query: {search_query}")

                # Perform web search using BrowserOS CDP
                search_results = asyncio.run(perform_web_search(search_query))
            except Exception as e:
                logger.error(f"Error generating/falling back to search query: {e}")
                return WebSearchOutput(response=f"An error occurred during the search: {str(e)}")

        # Check if we got an error response
        if search_results.startswith("Error:"):
            return WebSearchOutput(response=search_results)

        # Synthesize response using LLM
        synthesis_prompt = f"Based on the following search results, provide a comprehensive answer to: {input.prompt}\n\nSearch Results:\n{search_results}"
        final_response = ollama.chat(
            model='llama3.2',
            messages=[{'role': 'user', 'content': synthesis_prompt}],
            options={'timeout': 60, 'num_gpu': 0}  # Force CPU only
        )
        response = final_response['message']['content']

        return WebSearchOutput(response=response)

    except Exception as e:
        logger.error(f"Error in web search: {e}")
        # Attempt cleanup on error (but don't fail if cleanup fails)
        try:
            memory_usage = get_memory_usage()
            if memory_usage > 1000:  # If using over 1GB, cleanup
                logger.info("High memory usage detected, triggering cleanup...")
                cleanup_browseros()
        except Exception as cleanup_error:
            logger.error(f"Cleanup failed: {cleanup_error}")
        return WebSearchOutput(response=f"An error occurred during the search: {str(e)}")

if __name__ == "__main__":
    # Register cleanup only when running as main script
    atexit.register(cleanup_browseros)

    # Add signal handlers only when running as main script
    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        cleanup_browseros()
        exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    port = int(os.getenv("AGENT_PORT", 9502))
    host = os.getenv("AGENT_HOST", "127.0.0.1")
    app.settings.host = host
    app.settings.port = port
    app.run(transport="streamable-http")