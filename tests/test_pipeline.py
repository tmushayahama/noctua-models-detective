"""Tests for src.pipeline and src.steps."""

import pytest
from unittest.mock import MagicMock
from pathlib import Path
from src.pipeline import Pipeline
from src.steps import (
    PipelineContext,
    FULL_STEPS,
    LOG_ONLY_STEPS,
    REPO_ONLY_STEPS,
    CleanStep,
    FilterStep,
    ResolveOntologyStep,
    ResolveMetadataStep,
    HumanizeStep,
    ExtractVersionsStep,
    ResolveOntologyTtlStep,
    DiffStep,
    ChangelogStep,
    ReportStep,
)


class TestPipelineContext:
    def test_context_with_all_args(self):
        ctx = PipelineContext(
            output_dir=Path("/tmp/out"),
            model_id="abc123",
            log_file=Path("/tmp/log.log"),
            repo_path="/tmp/repo",
            after="2026-01-01",
        )
        assert ctx.model_id == "abc123"
        assert ctx.log_file == Path("/tmp/log.log")
        assert ctx.repo_path == "/tmp/repo"
        assert ctx.after == "2026-01-01"

    def test_context_defaults(self):
        ctx = PipelineContext(output_dir=Path("/tmp/out"), model_id="abc123")
        assert ctx.log_file is None
        assert ctx.repo_path is None
        assert ctx.after is None
        assert ctx.clean_path is None
        assert ctx.filtered_path is None
        assert ctx.models_dir is None
        assert ctx.labels == {}


class TestPipelineFromArgs:
    def test_full_mode(self):
        p = Pipeline.from_args(
            output_dir="/tmp/out",
            model_id="abc123",
            log_file="/tmp/log.log",
            repo_path="/tmp/repo",
        )
        assert p._steps is FULL_STEPS

    def test_log_only_mode(self):
        p = Pipeline.from_args(
            output_dir="/tmp/out",
            model_id="abc123",
            log_file="/tmp/log.log",
        )
        assert p._steps is LOG_ONLY_STEPS

    def test_repo_only_mode(self):
        p = Pipeline.from_args(
            output_dir="/tmp/out",
            model_id="abc123",
            repo_path="/tmp/repo",
        )
        assert p._steps is REPO_ONLY_STEPS

    def test_no_inputs_raises(self):
        with pytest.raises(ValueError, match="Must provide"):
            Pipeline.from_args(output_dir="/tmp/out", model_id="abc123")


class TestModeStepCounts:
    def test_full_has_10_steps(self):
        assert len(FULL_STEPS) == 10

    def test_log_only_has_6_steps(self):
        assert len(LOG_ONLY_STEPS) == 6

    def test_repo_only_has_5_steps(self):
        assert len(REPO_ONLY_STEPS) == 5


class TestModeStepOrder:
    def test_full_step_order(self):
        types = [type(s) for s in FULL_STEPS]
        assert types == [
            CleanStep, FilterStep, ResolveOntologyStep, ResolveMetadataStep,
            HumanizeStep, ExtractVersionsStep, ResolveOntologyTtlStep,
            DiffStep, ChangelogStep, ReportStep,
        ]

    def test_log_only_step_order(self):
        types = [type(s) for s in LOG_ONLY_STEPS]
        assert types == [
            CleanStep, FilterStep, ResolveOntologyStep,
            ResolveMetadataStep, HumanizeStep, ReportStep,
        ]

    def test_repo_only_step_order(self):
        types = [type(s) for s in REPO_ONLY_STEPS]
        assert types == [
            ResolveMetadataStep, ExtractVersionsStep,
            ResolveOntologyTtlStep, DiffStep, ChangelogStep,
        ]


class TestPipelineRun:
    def test_runs_all_steps_in_order(self, tmp_path, capsys):
        ctx = PipelineContext(output_dir=tmp_path, model_id="abc123")
        calls = []
        steps = []
        for name in ("step_a", "step_b", "step_c"):
            step = MagicMock()
            step.name = name
            step.run.side_effect = lambda c, n=name: calls.append(n)
            steps.append(step)

        Pipeline(ctx, steps).run()

        assert calls == ["step_a", "step_b", "step_c"]
        out = capsys.readouterr().out
        assert "[1/3] step_a" in out
        assert "[2/3] step_b" in out
        assert "[3/3] step_c" in out
        assert "Done." in out

    def test_creates_output_dir(self, tmp_path):
        out = tmp_path / "nested" / "dir"
        ctx = PipelineContext(output_dir=out, model_id="abc123")
        Pipeline(ctx, []).run()
        assert out.is_dir()


class TestStepNames:
    def test_all_steps_have_names(self):
        for step in FULL_STEPS:
            assert hasattr(step, "name")
            assert isinstance(step.name, str)
            assert len(step.name) > 0
