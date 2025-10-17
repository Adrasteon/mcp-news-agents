import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def validate_plan(plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate a plan produced by the LLM.

    Ensures each item is a dict with an allowed action.
    Raises ValueError on invalid input.
    """
    if not isinstance(plan, list):
        raise ValueError("Plan must be a list of action objects")

    validated: List[Dict[str, Any]] = []
    allowed = {"goto", "wait", "click", "fill", "press", "extract", "extract_list", "eval_js", "screenshot"}
    for i, a in enumerate(plan):
        if not isinstance(a, dict) or 'action' not in a:
            raise ValueError(f"Invalid action at index {i}: missing 'action' field")
        if a['action'] not in allowed:
            raise ValueError(f"Invalid action '{a['action']}' at index {i}")
        validated.append(a)
    return validated


def execute_plan(plan: List[Dict[str, Any]], client, stop_on_error: bool = True) -> Dict[str, Any]:
    """Execute a validated plan step-by-step using the provided client.

    client must provide a `send_action(action: Dict) -> Dict` method.
    Returns a dict with execution metadata and per-step outputs.
    """
    outputs = []
    for idx, act in enumerate(plan):
        action_attempts = act.get('retries', 2)
        backoff_base = act.get('backoff', 0.5)
        attempt = 0
        success = False
        last_err = None
        while attempt <= action_attempts:
            try:
                logger.info(f"Executing action {idx+1}/{len(plan)} attempt {attempt+1}: {act.get('action')}")
                res = client.send_action(act)
                outputs.append({"action": act, "result": res})
                # If a step reports isError via Klavis wrapper, treat as failure
                if isinstance(res, dict) and res.get('isError'):
                    last_err = res
                    logger.warning(f"Action {idx} reported isError: {res}")
                    raise RuntimeError(f"Action reported isError: {res}")
                success = True
                break
            except Exception as e:
                last_err = e
                logger.warning(f"Action {idx} attempt {attempt+1} failed: {e}")
                # Try to capture a screenshot/artifact for diagnostics if supported
                try:
                    session_id = act.get('session_id')
                    artifact_bytes = None
                    if hasattr(client, 'get_screenshot') and session_id:
                        artifact_bytes = client.get_screenshot(session_id)
                    elif hasattr(client, 'get_screenshot') and not session_id:
                        # Try best-effort without session id
                        artifact_bytes = client.get_screenshot('')

                    if artifact_bytes:
                        import base64
                        encoded = base64.b64encode(artifact_bytes).decode('ascii')
                        outputs.append({"action": act, "artifact_screenshot_base64": encoded})
                except Exception as art_e:
                    logger.debug(f"Failed to capture artifact for action {idx}: {art_e}")

                attempt += 1
                if attempt > action_attempts:
                    logger.error(f"Action {idx} failed after {attempt} attempts: {last_err}")
                    outputs.append({"action": act, "result": {"success": False, "error": str(last_err)}})
                    if stop_on_error:
                        return {"executed": len(outputs), "outputs": outputs}
                    break
                # exponential-ish backoff
                try:
                    sleep_for = backoff_base * (2 ** (attempt - 1))
                    logger.info(f"Sleeping for {sleep_for}s before retrying action {idx}")
                    import time
                    time.sleep(sleep_for)
                except Exception:
                    pass

    return {"executed": len(outputs), "outputs": outputs}
