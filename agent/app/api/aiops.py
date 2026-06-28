
"""
AIOps operations API
"""

import json
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from loguru import logger

from app.models.aiops import AIOpsRequest
from app.services.aiops_service import aiops_service

router = APIRouter()


@router.post("/aiops")
async def diagnose_stream(request: AIOpsRequest):
    """
    AIOps fault diagnosis API, streaming SSE

    **Function description:**
    - Automatically fetch current active system alerts
    - Use Plan-Execute-Replan mode for intelligent diagnosis
    - Stream diagnosis process and results

    **SSE Event types:**

    1. `status` - Statusupdate
       ```json
       {
         "type": "status",
         "stage": "fetching_alerts",
         "message": "Fetching system alert information..."
       }
       ```

    2. `plan` - Diagnosis plan created
       ```json
       {
         "type": "plan",
         "stage": "plan_created",
         "message": "Diagnosis plan created with 6 steps",
         "target_alert": {...},
         "plan": ["Step 1: ...", "Step 2: ..."]
       }
       ```

    3. `step_complete` - Step completed
       ```json
       {
         "type": "step_complete",
         "stage": "step_executed",
         "message": "Step completed (2/6)",
         "current_step": "query system logs",
         "result_preview": "...",
         "remaining_steps": 4
       }
       ```

    4. `report` - Final diagnosis report
       ```json
       {
         "type": "report",
         "stage": "final_report",
         "message": "Final diagnosis report generated",
         "report": "# Fault diagnosis report\\n...",
         "evidence": {...}
       }
       ```

    5. `complete` - Diagnosis completed
       ```json
       {
         "type": "complete",
         "stage": "diagnosis_complete",
         "message": "Diagnosis flow completed",
         "diagnosis": {...}
       }
       ```

    6. `error` - error information
       ```json
       {
         "type": "error",
         "stage": "error",
         "message": "Diagnosis process error: ..."
       }
       ```

    **Usage example:**
    ```bash
    curl -X POST "http://localhost:9900/api/aiops" \\
      -H "Content-Type: application/json" \\
      -d '{"session_id": "session-123"}' \\
      --no-buffer
    ```

    **Frontend usage example:**
    ```javascript
    const eventSource = new EventSource('/api/aiops');

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'plan') {
        console.log('Diagnosis plan:', data.plan);
      } else if (data.type === 'step_complete') {
        console.log('Step completed:', data.current_step);
      } else if (data.type === 'report') {
        console.log('Final report:', data.report);
      } else if (data.type === 'complete') {
        console.log('Diagnosis completed');
        eventSource.close();
      }
    };
    ```

    Args:
        request: AIOps diagnosis request

    Returns:
        SSE event stream
    """
    session_id = request.session_id or "default"
    logger.info(f"[session {session_id}] received AIOps diagnosis request (streaming)")

    async def event_generator():
        try:
            async for event in aiops_service.diagnose(session_id=session_id):
                # Send event
                yield {
                    "event": "message",
                    "data": json.dumps(event, ensure_ascii=False)
                }

                # End stream if event is complete or error
                if event.get("type") in ["complete", "error"]:
                    break

            logger.info(f"[session {session_id}] AIOps diagnosis streaming response completed")

        except Exception as e:
            logger.error(f"[session {session_id}] AIOps diagnosis streaming response exception: {e}", exc_info=True)
            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "error",
                    "stage": "exception",
                    "message": f"Diagnosis exception: {str(e)}"
                }, ensure_ascii=False)
            }

    return EventSourceResponse(event_generator())
