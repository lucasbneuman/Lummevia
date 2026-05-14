from lummevia_evaluations import EvaluationStatus, PromptEvaluation, PromptEvaluationRegistry
from lummevia_learning import (
    InsightType,
    LearningAnalysisContext,
    LearningAnalyzer,
    LearningRegistry,
    RecommendationType,
    generate_recommendations,
)
from lummevia_memory import MemoryCategory, ProjectMemoryRegistry
from lummevia_runtime import DevelopmentRuntime
from lummevia_runtime.learning import analyze_learning_for_runtime
from lummevia_timeline import TimelineRegistry


def test_repeated_qa_failures_generate_quality_insight() -> None:
    analyzer = LearningAnalyzer()
    signals, insights = analyzer.analyze(
        LearningAnalysisContext(
            project="lummevia-os",
            source_type="TEST",
            source_id="qa-repeat",
            qa_failure_count=3,
        )
    )

    assert any(signal.signal_type.value == "QA_FAILURES_REPEATED" for signal in signals)
    assert any(insight.insight_type == InsightType.QUALITY for insight in insights)


def test_high_cost_generates_model_lite_recommendation() -> None:
    _, insights = LearningAnalyzer().analyze(
        LearningAnalysisContext(
            project="lummevia-os",
            source_type="TEST",
            source_id="high-cost",
            estimated_cost_total=5.5,
            cost_control_status="WARN",
        )
    )
    recommendations = generate_recommendations(
        project="lummevia-os",
        insights=insights,
    )

    assert any(
        recommendation.recommendation_type == RecommendationType.USE_MODEL_LITE
        for recommendation in recommendations
    )


def test_low_prompt_score_generates_prompt_quality_insight() -> None:
    PromptEvaluationRegistry.default().register(
        PromptEvaluation(
            evaluation_id="eval-learning-low-prompt",
            template_id="pm_business_brief",
            template_version="v1",
            provider="FAKE",
            model="fake:model",
            score=0.42,
            status=EvaluationStatus.NEEDS_REVIEW,
            metadata={"project": "lummevia-os"},
        )
    )
    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-LEARN-PROMPT")

    assert any(
        insight["insight_type"] == InsightType.PROMPT_QUALITY.value
        for insight in state.metadata["insights"]
    )


def test_dead_letters_generate_resilience_insight() -> None:
    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-LEARN-DEAD")
    result = analyze_learning_for_runtime(
        state,
        context_overrides={"dead_letter_count": 1},
    )

    assert any(
        insight.insight_type == InsightType.RESILIENCE for insight in result["insights"]
    )


def test_recommendation_requires_review_and_project_memory_receives_insight() -> None:
    PromptEvaluationRegistry.default().register(
        PromptEvaluation(
            evaluation_id="eval-learning-review",
            template_id="pm_business_brief",
            template_version="v1",
            provider="FAKE",
            model="fake:model",
            score=0.4,
            status=EvaluationStatus.NEEDS_REVIEW,
            metadata={"project": "lummevia-os"},
        )
    )
    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-LEARN-MEM")

    recommendation = LearningRegistry.default().list_recommendations(project="lummevia-os")[0]
    assert recommendation.requires_human_review is True
    assert recommendation.metadata["review_id"].startswith("review-")

    records = ProjectMemoryRegistry.default().list_project_memories("lummevia-os")
    assert any(record.metadata.get("insight_id") for record in records)
    assert any(
        record.category
        in {
            MemoryCategory.PROMPT_LEARNING,
            MemoryCategory.TASK_LEARNING,
            MemoryCategory.QA_ISSUE,
            MemoryCategory.IMPLEMENTATION_NOTE,
        }
        for record in records
    )
    assert state.metadata["insight_count"] >= 1


def test_timeline_contains_learning_events() -> None:
    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-LEARN-TIMELINE")
    analyze_learning_for_runtime(
        state,
        context_overrides={"qa_failure_count": 2},
    )
    timeline = TimelineRegistry.default().get_timeline(state.run.run_id)

    assert timeline is not None
    event_types = {event.event_type for event in timeline.events}
    assert "LEARNING_SIGNAL_CREATED" in event_types
    assert "OPERATIONAL_INSIGHT_CREATED" in event_types
    assert "OPTIMIZATION_RECOMMENDATION_CREATED" in event_types
