import pytest

from app.engines.country import underlying
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"

RATES = {"food": 6.0, "energy": 12.0, "shelter": 4.0, "core_goods": 2.0}
WEIGHTS = {"food": 0.2, "energy": 0.1, "shelter": 0.5, "core_goods": 0.2}


def cfg(**overrides):
    defaults = dict(
        preferred_method="weighted_median",
        fallback_methods=("trimmed_mean", "official_core"),
        trim_alpha=0.1,
        trim_beta=0.1,
        excluded_categories=("food", "energy"),
    )
    defaults.update(overrides)
    return underlying.UnderlyingConfig(**defaults)


class TestAllMethodsComputed:
    def test_returns_all_four_named_components(self):
        result = underlying.calculate(
            component_rates=RATES,
            component_weights=WEIGHTS,
            config=cfg(),
            geography="USA",
            period="2026-06",
            calculated_at=CALCULATED_AT,
        )
        keys = {c.key for c in result.components}
        assert keys == {"weighted_median_value", "trimmed_mean_value", "core_value", "model_based_value"}

    def test_model_based_always_unavailable_in_v1(self):
        result = underlying.calculate(
            component_rates=RATES, component_weights=WEIGHTS, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        model_based = next(c for c in result.components if c.key == "model_based_value")
        assert model_based.value is None
        assert any("model_based unavailable" in w for w in result.warnings)

    def test_core_exclusion_matches_manual_formula(self):
        result = underlying.calculate(
            component_rates=RATES, component_weights=WEIGHTS, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        core = next(c for c in result.components if c.key == "core_value")
        retained_weight = WEIGHTS["shelter"] + WEIGHTS["core_goods"]
        expected = (WEIGHTS["shelter"] * RATES["shelter"] + WEIGHTS["core_goods"] * RATES["core_goods"]) / retained_weight
        assert core.value == pytest.approx(expected)

    def test_official_core_value_overrides_derived_computation(self):
        result = underlying.calculate(
            component_rates=RATES, component_weights=WEIGHTS, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            official_core_value=3.1,
        )
        core = next(c for c in result.components if c.key == "core_value")
        assert core.value == pytest.approx(3.1)

    def test_component_labels_and_official_vs_derived(self):
        # Derived core has label "Core (derived)"
        result_derived = underlying.calculate(
            component_rates=RATES, component_weights=WEIGHTS, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        labels_by_key = {c.key: c.label for c in result_derived.components}
        assert labels_by_key["weighted_median_value"] == "Weighted Median"
        assert labels_by_key["trimmed_mean_value"] == "Trimmed Mean"
        assert labels_by_key["model_based_value"] == "Model Based"
        assert labels_by_key["core_value"] == "Core (derived)"

        # Published official core has label "Official Value"
        result_official = underlying.calculate(
            component_rates=RATES, component_weights=WEIGHTS, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            official_core_value=3.1,
        )
        core_comp = next(c for c in result_official.components if c.key == "core_value")
        assert core_comp.label == "Official Value"



class TestMethodSelection:
    def test_selects_preferred_method(self):
        result = underlying.calculate(
            component_rates=RATES, component_weights=WEIGHTS, config=cfg(preferred_method="weighted_median"),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.metadata["selected_method"] == "weighted_median"
        wm = next(c for c in result.components if c.key == "weighted_median_value")
        assert result.value == pytest.approx(wm.value)

    def test_selection_does_not_pick_extreme_result(self):
        # regression guard: selection must follow config order, not min/max
        result = underlying.calculate(
            component_rates=RATES, component_weights=WEIGHTS, config=cfg(preferred_method="official_core"),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        core = next(c for c in result.components if c.key == "core_value")
        assert result.value == pytest.approx(core.value)
        assert result.metadata["selected_method"] == "official_core"

    def test_falls_back_when_preferred_unavailable(self):
        # single-category input makes trimmed_mean/weighted_median trivial
        # but core exclusion impossible if all categories are excluded
        rates = {"food": 5.0, "energy": 9.0}
        weights = {"food": 0.5, "energy": 0.5}
        result = underlying.calculate(
            component_rates=rates,
            component_weights=weights,
            config=cfg(preferred_method="official_core", fallback_methods=("weighted_median",), excluded_categories=("food", "energy")),
            geography="USA",
            period="2026-06",
            calculated_at=CALCULATED_AT,
        )
        assert result.metadata["selected_method"] == "weighted_median"

    def test_all_methods_unavailable_returns_unavailable_result(self):
        result = underlying.calculate(
            component_rates={}, component_weights={}, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value is None
        assert result.coverage == Coverage.UNAVAILABLE
        assert result.metadata["selected_method"] is None


class TestEdgeCases:
    def test_zero_growth_all_components(self):
        rates = {"food": 0.0, "energy": 0.0, "shelter": 0.0}
        weights = {"food": 0.3, "energy": 0.3, "shelter": 0.4}
        result = underlying.calculate(
            component_rates=rates, component_weights=weights, config=cfg(excluded_categories=("energy",)),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value == pytest.approx(0.0)

    def test_deflation_case(self):
        rates = {"food": -2.0, "energy": -5.0, "shelter": -1.0}
        weights = {"food": 0.3, "energy": 0.3, "shelter": 0.4}
        result = underlying.calculate(
            component_rates=rates, component_weights=weights, config=cfg(excluded_categories=()),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value < 0

    def test_weights_not_summing_to_one_marks_that_method_unavailable(self):
        rates = {"food": 5.0, "shelter": 3.0}
        weights = {"food": 0.5, "shelter": 0.6}  # sums to 1.1
        result = underlying.calculate(
            component_rates=rates, component_weights=weights, config=cfg(excluded_categories=()),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        wm = next(c for c in result.components if c.key == "weighted_median_value")
        assert wm.value is None

    def test_extreme_inflation_component(self):
        rates = {"food": 5.0, "energy": 900.0, "shelter": 3.0}
        weights = {"food": 0.3, "energy": 0.3, "shelter": 0.4}
        result = underlying.calculate(
            component_rates=rates, component_weights=weights, config=cfg(excluded_categories=("energy",)),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        core = next(c for c in result.components if c.key == "core_value")
        assert core.value < 10  # excluding the extreme energy component keeps core moderate


class TestHandleUnderlyingProfileFormats:
    def test_single_string_excluded_categories_and_fallbacks(self):
        from app.api.country import _handle_underlying

        profile = {
            "underlying": {
                "preferred_method": "official_core",
                "fallback_methods": "trimmed_mean",
                "trimmed_mean": {"alpha": 0.1, "beta": 0.1},
                "core_exclusion": {
                    "excluded_categories": "energy",
                },
            }
        }
        body = {
            "component_rates": {"food": 5.0, "energy": 900.0, "shelter": 3.0},
            "component_weights": {"food": 0.3, "energy": 0.3, "shelter": 0.4},
            "period": "2026-06",
        }
        result = _handle_underlying("USA", body, profile)
        core = next(c for c in result.components if c.key == "core_value")
        # energy (900.0) must be excluded, not retained because of ('e','n','e','r','g','y')!
        assert core.value < 10
        assert result.metadata["selected_method"] == "official_core"

    def test_empty_string_or_none_excluded_categories(self):
        from app.api.country import _handle_underlying

        profile = {
            "underlying": {
                "preferred_method": "weighted_median",
                "fallback_methods": "",
                "trimmed_mean": {},
                "core_exclusion": {
                    "excluded_categories": None,
                },
            }
        }
        body = {
            "component_rates": {"food": 5.0, "shelter": 3.0},
            "component_weights": {"food": 0.5, "shelter": 0.5},
            "period": "2026-06",
        }
        result = _handle_underlying("USA", body, profile)
        assert result.value is not None

