"""
Workflow Generator Service.

Converts a validated WorkflowInstruction into the JSON payload that is
posted to the n8n execution webhook.
"""
from ..logging_config import get_logger
from ..schemas import WorkflowInstruction

logger = get_logger(__name__)


class WorkflowGeneratorService:
    @staticmethod
    def generate_payload(
        instruction: WorkflowInstruction,
        run_id: int,
        raw_request: str,
        correlation_id: str,
    ) -> dict:
        """
        Build a structured webhook payload from a WorkflowInstruction.

        The payload is forwarded as-is to the n8n execution webhook and also
        persisted in the database for auditing purposes.
        """
        instruction_data = instruction.model_dump()
        payload = {
            "run_id": run_id,
            "correlation_id": correlation_id,
            "workflow_name": instruction_data["workflow_name"],
            "trigger": instruction_data["trigger"],
            "steps": instruction_data["steps"],
            "channels": instruction_data["channels"],
            "output_format": instruction_data["output_format"],
            "raw_request": raw_request,
        }
        logger.debug(
            "Generated workflow payload | run_id=%s | workflow=%s | steps=%d",
            run_id,
            payload["workflow_name"],
            len(payload["steps"]),
        )
        return payload
