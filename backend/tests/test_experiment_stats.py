"""洞察工坊 · 实验统计和显著性测试

测试 A/B 实验的统计显著性检验、分流正确性和提升幅度计算。
"""
from __future__ import annotations

import pytest

from app.models import (
    ABExperiment,
    AggregationMethod,
    ExperimentResult,
    ExperimentStatus,
    MetricDataSource,
    MetricDef,
    MetricPeriod,
    Segment,
    UserSegmentCompare,
)


class TestABExperiment:
    def test_deterministic_split(self):
        exp = ABExperiment(
            experiment_id="EXP_SPLIT",
            experiment_name="分流测试",
            groups={"control": 0.5, "treatment": 0.5},
            split_ratio={"control": 0.5, "treatment": 0.5},
        )
        # Same user always gets same group
        group1 = exp.assign_group("user_12345")
        group2 = exp.assign_group("user_12345")
        assert group1 == group2

    def test_split_distribution(self):
        exp = ABExperiment(
            experiment_id="EXP_DIST",
            experiment_name="分布测试",
            groups={"control": 0.5, "treatment": 0.5},
            split_ratio={"control": 0.5, "treatment": 0.5},
        )
        groups = {}
        for i in range(1000):
            g = exp.assign_group(f"user_{i}")
            groups[g] = groups.get(g, 0) + 1
        # 1000 users, 50/50 split should be roughly balanced
        assert 400 <= groups.get("control", 0) <= 600
        assert 400 <= groups.get("treatment", 0) <= 600

    def test_split_with_three_groups(self):
        exp = ABExperiment(
            experiment_id="EXP_THREE",
            experiment_name="三组实验",
            groups={"control": 0.2, "treatment_a": 0.4, "treatment_b": 0.4},
            split_ratio={"control": 0.2, "treatment_a": 0.4, "treatment_b": 0.4},
        )
        groups = {}
        for i in range(1000):
            g = exp.assign_group(f"user_{i}")
            groups[g] = groups.get(g, 0) + 1
        # 20/40/40 split
        assert 100 <= groups.get("control", 0) <= 300
        assert 300 <= groups.get("treatment_a", 0) <= 500
        assert 300 <= groups.get("treatment_b", 0) <= 500

    def test_assign_group_all_users(self):
        exp = ABExperiment(
            experiment_id="EXP_ALL",
            experiment_name="全覆盖测试",
            groups={"control": 1.0},
            split_ratio={"control": 1.0},
        )
        assert exp.assign_group("user_abc") == "control"


class TestTTest:
    def test_significant_difference(self):
        """Test: two groups with clear difference should be significant."""
        compare = UserSegmentCompare(
            compare_id="TEST_SIG",
            segment_a=Segment(segment_id="A", segment_name="Group A"),
            segment_b=Segment(segment_id="B", segment_name="Group B"),
            compare_metric=MetricDef(
                metric_id="M1", metric_name="metric",
                calculation_formula="", aggregation=AggregationMethod.AVG,
                data_source=MetricDataSource.CLICKHOUSE,
                period=MetricPeriod.DAILY, owner="test",
                field_name="val", table_name="test",
            ),
            data_a=[10.0, 12.0, 11.0, 13.0, 10.0, 12.0, 11.0, 13.0],  # mean=11.5
            data_b=[20.0, 22.0, 21.0, 23.0, 20.0, 22.0, 21.0, 23.0],  # mean=21.5
        )
        result = compare.compute_ttest()
        assert result["significant"] is True
        assert result["p_value"] < 0.001
        assert abs(result["t_stat"]) > 0

    def test_no_significant_difference(self):
        """Test: two groups with similar means should not be significant."""
        compare = UserSegmentCompare(
            compare_id="TEST_NOSIG",
            segment_a=Segment(segment_id="A", segment_name="Group A"),
            segment_b=Segment(segment_id="B", segment_name="Group B"),
            compare_metric=MetricDef(
                metric_id="M2", metric_name="metric",
                calculation_formula="", aggregation=AggregationMethod.AVG,
                data_source=MetricDataSource.CLICKHOUSE,
                period=MetricPeriod.DAILY, owner="test",
                field_name="val", table_name="test",
            ),
            data_a=[10.0, 11.0, 10.5, 10.8, 10.2, 11.2, 10.6, 10.9],
            data_b=[10.5, 10.8, 10.3, 11.0, 10.7, 10.9, 10.4, 11.1],
        )
        result = compare.compute_ttest()
        assert result["significant"] is False
        assert result["p_value"] > 0.05

    def test_insufficient_sample_size(self):
        """Test: groups with < 2 samples should return not significant."""
        compare = UserSegmentCompare(
            compare_id="TEST_SMALL",
            segment_a=Segment(segment_id="A", segment_name="Group A"),
            segment_b=Segment(segment_id="B", segment_name="Group B"),
            compare_metric=MetricDef(
                metric_id="M3", metric_name="metric",
                calculation_formula="", aggregation=AggregationMethod.AVG,
                data_source=MetricDataSource.CLICKHOUSE,
                period=MetricPeriod.DAILY, owner="test",
                field_name="val", table_name="test",
            ),
            data_a=[10.0],
            data_b=[20.0, 21.0],
        )
        result = compare.compute_ttest()
        assert result["significant"] is False
        assert result["reason"] == "样本不足"

    def test_equal_means(self):
        """Test: identical data should have p_value close to 1."""
        import math
        data = [10.0, 12.0, 11.0, 13.0, 10.0, 12.0, 11.0, 13.0]
        compare = UserSegmentCompare(
            compare_id="TEST_EQ",
            segment_a=Segment(segment_id="A", segment_name="Group A"),
            segment_b=Segment(segment_id="B", segment_name="Group B"),
            compare_metric=MetricDef(
                metric_id="M4", metric_name="metric",
                calculation_formula="", aggregation=AggregationMethod.AVG,
                data_source=MetricDataSource.CLICKHOUSE,
                period=MetricPeriod.DAILY, owner="test",
                field_name="val", table_name="test",
            ),
            data_a=data,
            data_b=data,
        )
        result = compare.compute_ttest()
        assert result["t_stat"] == 0.0
        # p_value should be 1.0 when groups are identical
        assert math.isclose(result["p_value"], 1.0, abs_tol=0.01)

    def test_ttest_is_deterministic(self):
        data_a = [10.0, 12.0, 11.0, 13.0, 10.0, 12.0, 11.0, 13.0]
        data_b = [20.0, 22.0, 21.0, 23.0, 20.0, 22.0, 21.0, 23.0]
        compare = UserSegmentCompare(
            compare_id="TEST_DET",
            segment_a=Segment(segment_id="A", segment_name="Group A"),
            segment_b=Segment(segment_id="B", segment_name="Group B"),
            compare_metric=MetricDef(
                metric_id="M5", metric_name="metric",
                calculation_formula="", aggregation=AggregationMethod.AVG,
                data_source=MetricDataSource.CLICKHOUSE,
                period=MetricPeriod.DAILY, owner="test",
                field_name="val", table_name="test",
            ),
            data_a=data_a, data_b=data_b,
        )
        r1 = compare.compute_ttest()
        r2 = compare.compute_ttest()
        assert r1 == r2


class TestExperimentResult:
    def test_analyze_computes_lift(self):
        metric = MetricDef(
            metric_id="M_LIFT", metric_name="转化率",
            calculation_formula="COUNT(conversions)/COUNT(users)",
            aggregation=AggregationMethod.AVG,
            data_source=MetricDataSource.CLICKHOUSE,
            period=MetricPeriod.DAILY, owner="test",
            field_name="rate", table_name="test",
        )
        exp = ABExperiment(
            experiment_id="EXP_LIFT", experiment_name="Lift测试",
            groups={"control": 0.5, "treatment": 0.5},
            split_ratio={"control": 0.5, "treatment": 0.5},
            evaluation_metrics=[metric],
        )
        result = ExperimentResult(
            report_id="RPT_LIFT",
            experiment=exp,
            metric=metric,
            control_data=[0.10, 0.12, 0.11, 0.13, 0.10, 0.12, 0.11, 0.13],
            treatment_data=[0.15, 0.17, 0.16, 0.18, 0.15, 0.17, 0.16, 0.18],
        )
        analyzed = result.analyze()
        assert analyzed.lift > 0
        assert analyzed.significant is True
        assert analyzed.control_mean > 0
        assert analyzed.treatment_mean > analyzed.control_mean

    def test_no_lift_when_same_data(self):
        import math
        metric = MetricDef(
            metric_id="M_NOLIFT", metric_name="测试",
            calculation_formula="",
            aggregation=AggregationMethod.AVG,
            data_source=MetricDataSource.CLICKHOUSE,
            period=MetricPeriod.DAILY, owner="test",
            field_name="val", table_name="test",
        )
        exp = ABExperiment(
            experiment_id="EXP_NOLIFT", experiment_name="无提升",
            groups={"control": 0.5, "treatment": 0.5},
            split_ratio={"control": 0.5, "treatment": 0.5},
            evaluation_metrics=[metric],
        )
        data = [100.0, 102.0, 101.0, 103.0]
        result = ExperimentResult(
            report_id="RPT_NOLIFT",
            experiment=exp,
            metric=metric,
            control_data=data,
            treatment_data=data,
        )
        analyzed = result.analyze()
        assert math.isclose(analyzed.lift, 0.0, abs_tol=0.01)
        assert analyzed.significant is False