from __future__ import annotations

from math import ceil

from lummevia_economics.schemas import UsageEstimate


DEFAULT_FAKE_PRICING = {
    "strong": {"input_per_1k": 0.12, "output_per_1k": 0.24},
    "lite": {"input_per_1k": 0.03, "output_per_1k": 0.06},
    "fake": {"input_per_1k": 0.0, "output_per_1k": 0.0},
}


class CostEstimator:
    _default_instance: "CostEstimator | None" = None

    def __init__(
        self,
        *,
        pricing_table: dict[str, dict[str, float]] | None = None,
        chars_per_token: int = 4,
        default_output_ratio: float = 0.5,
    ) -> None:
        self.pricing_table = pricing_table or DEFAULT_FAKE_PRICING
        self.chars_per_token = max(chars_per_token, 1)
        self.default_output_ratio = max(default_output_ratio, 0.0)

    @classmethod
    def default(cls) -> "CostEstimator":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def estimate_usage(
        self,
        *,
        project: str,
        provider: str,
        model: str,
        role: str,
        operation_type: str,
        prompt_length: int,
        output_length: int | None = None,
        workflow_run_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> UsageEstimate:
        effective_output_length = (
            output_length
            if output_length is not None
            else int(prompt_length * self.default_output_ratio)
        )
        input_tokens = self.estimate_tokens(prompt_length)
        output_tokens = self.estimate_tokens(effective_output_length)
        tier = self.resolve_tier(provider=provider, model=model)
        pricing = self.pricing_table[tier]
        estimated_cost = round(
            (input_tokens / 1000.0) * pricing["input_per_1k"]
            + (output_tokens / 1000.0) * pricing["output_per_1k"],
            6,
        )
        return UsageEstimate(
            project=project,
            workflow_run_id=workflow_run_id,
            provider=provider,
            model=model,
            role=role,
            operation_type=operation_type,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            estimated_cost=estimated_cost,
            metadata={
                "prompt_length": prompt_length,
                "output_length": effective_output_length,
                "cost_tier": tier,
                **(metadata or {}),
            },
        )

    def estimate_tokens(self, text_length: int) -> int:
        if text_length <= 0:
            return 0
        return ceil(text_length / self.chars_per_token)

    def resolve_tier(self, *, provider: str, model: str) -> str:
        provider_upper = provider.upper()
        model_lower = model.lower()
        if provider_upper == "FAKE" or "fake" in model_lower:
            return "fake"
        if "strong" in model_lower or "chat" in model_lower or "pro" in model_lower:
            return "strong"
        return "lite"
