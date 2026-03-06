from ..schemas import WorkflowInstruction


class WorkflowGeneratorService:
    @staticmethod
    def generate_payload(
        instruction: WorkflowInstruction,
        run_id: int,
        raw_request: str,
        correlation_id: str,
    ) -> dict:
        instruction_data = instruction.model_dump()
        return {
            "run_id": run_id,
            "correlation_id": correlation_id,
            "workflow_name": instruction_data["workflow_name"],
            "trigger": instruction_data["trigger"],
            "steps": instruction_data["steps"],
            "channels": instruction_data["channels"],
            "output_format": instruction_data["output_format"],
            "raw_request": raw_request,
        }
