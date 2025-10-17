# news-admin-client: Web dashboard for news multi-agent system
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import requests
from prometheus_client import start_http_server, Counter, Gauge

PROMETHEUS_URL = "http://localhost:9090"

app = FastAPI(title="News Admin Dashboard")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

REQUESTS = Counter('requests_total', 'Total requests to admin client')
CLIENT_STATUS = Gauge('client_status', 'Status of the admin client (1=up, 0=down)')

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/agents")
def get_agents():
    # TODO: Query all MCP agents for status
    return JSONResponse([{"name": "news-research-agent", "status": "online"},
                        {"name": "news-analyzer-agent", "status": "online"},
                        {"name": "news-database-server", "status": "online"}])

@app.get("/api/metrics")
def get_metrics():
    # Query Prometheus for some example metrics
    try:
        r = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": "up"})
        data = r.json()
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/trigger/{agent}")
def trigger_agent(agent: str):
    # TODO: Trigger workflow for the specified agent
    return JSONResponse({"result": f"Triggered {agent}"})

@app.get("/api/issues")
def get_issues():
    # TODO: Query and return current issues/errors from all agents
    return JSONResponse([])

@app.post("/api/resolve/{issue_id}")
def resolve_issue(issue_id: str):
    # TODO: Resolve the specified issue
    return JSONResponse({"result": f"Resolved issue {issue_id}"})

if __name__ == "__main__":
    start_http_server(8011)
    CLIENT_STATUS.set(1)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
