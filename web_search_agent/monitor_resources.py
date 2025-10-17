#!/usr/bin/env python3
"""
Resource monitoring script for web-search-agent.
Checks BrowserOS process status and system resources.
"""
import subprocess
import psutil
import time
import os
import signal
import sys

def get_browseros_processes():
    """Find all BrowserOS processes."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
        try:
            if 'BrowserOS' in proc.info['name'] or 'browseros' in ' '.join(proc.info['cmdline'] or []):
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes

def monitor_resources():
    """Monitor system and BrowserOS resources."""
    print("=== Web Search Agent Resource Monitor ===")

    # System memory
    memory = psutil.virtual_memory()
    print(".1f"".1f"".1f")

    # BrowserOS processes
    browseros_procs = get_browseros_processes()
    print(f"\nBrowserOS processes found: {len(browseros_procs)}")

    for i, proc in enumerate(browseros_procs):
        try:
            memory_mb = proc.memory_info().rss / 1024 / 1024
            cpu_percent = proc.cpu_percent(interval=1)
            print(".1f"".1f")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"  Process {i+1}: Error accessing - {e}")

    # GPU memory (if available)
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines):
                used, total = line.split(',')
                print(f"GPU {i}: {used.strip()}/{total.strip()} MB")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("GPU monitoring not available (nvidia-smi not found)")

def cleanup_browseros():
    """Force cleanup of BrowserOS processes."""
    print("\n=== Cleaning up BrowserOS processes ===")
    browseros_procs = get_browseros_processes()

    for proc in browseros_procs:
        try:
            print(f"Terminating BrowserOS process {proc.pid}...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
                print(f"  Process {proc.pid} terminated gracefully")
            except psutil.TimeoutExpired:
                print(f"  Process {proc.pid} didn't respond, killing...")
                proc.kill()
                proc.wait()
                print(f"  Process {proc.pid} killed")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"  Error terminating process {proc.pid}: {e}")

    # Clean up temp directories
    temp_dirs = ['/tmp/browseros-data']
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                print(f"Error cleaning temp directory {temp_dir}: {e}")

def signal_handler(signum, frame):
    """Handle cleanup signal."""
    print(f"\nReceived signal {signum}, performing cleanup...")
    cleanup_browseros()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if len(sys.argv) > 1 and sys.argv[1] == 'cleanup':
        cleanup_browseros()
    else:
        print("Monitoring resources... (Ctrl+C to stop, or run with 'cleanup' to force cleanup)")
        try:
            while True:
                monitor_resources()
                print("\n" + "="*50)
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")