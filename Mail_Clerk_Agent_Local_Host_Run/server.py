from fastapi import FastAPI, BackgroundTasks
from agent import MailClerkAgent

app = FastAPI(title="Mail Clerk Agent API")

@app.get("/")
def read_root():
    return {"status": "Mail Clerk Agent running"}

@app.post("/run")
def trigger_agent_sync():
    """Synchronous trigger that executes processing immediately and returns detailed results."""
    agent = MailClerkAgent()
    results = agent.process_incoming_emails()
    return {"processed_count": len(results), "results": results}

@app.post("/trigger-run")
def trigger_agent_async(background_tasks: BackgroundTasks):
    """Asynchronous trigger that runs processing in the background to avoid connection timeouts."""
    agent = MailClerkAgent()
    background_tasks.add_task(agent.process_incoming_emails)
    return {"message": "Mail clerk run initiated in background."}