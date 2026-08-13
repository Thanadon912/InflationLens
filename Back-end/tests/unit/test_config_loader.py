import pytest

from app.config.loader import (
    ConfigError,
    available_country_profiles,
    load_country_profile,
    load_global_weights,
    load_indicator_registry,
    load_methodology_versions,
    load_yaml,
)


class TestLoadYaml:
    def test_missing_file_raises_config_error(self, tmp_path):
        with pytest.raises(ConfigError):
            load_yaml(tmp_path / "does_not_exist.yaml")

    def test_empty_file_raises(self, tmp_path):
        p = tmp_path / "empty.yaml"
        p.write_text("")
        with pytest.raises(ConfigError):
            load_yaml(p)

    def test_non_mapping_top_level_raises(self, tmp_path):
        p = tmp_path / "list.yaml"
        p.write_text("- a\n- b\n")
        with pytest.raises(ConfigError):
            load_yaml(p)

    def test_valid_file_loads(self, tmp_path):
        p = tmp_path / "ok.yaml"
        p.write_text("key: value\nnum: 1\n")
        data = load_yaml(p)
        assert data == {"key": "value", "num": 1}


class TestBundledConfigFiles:
    def test_indicator_registry_has_10_country_and_8_global(self):
        registry = load_indicator_registry()
        assert len(registry["country"]) == 10
        assert len(registry["global"]) == 8

    def test_methodology_versions_covers_all_18_indicators(self):
        versions = load_methodology_versions()
        assert len(versions["country"]) == 10
        assert len(versions["global"]) == 8
        for v in {**versions["country"], **versions["global"]}.values():
            assert v == "1.0.0"

    def test_global_weights_has_coverage_thresholds(self):
        weights = load_global_weights()
        thresholds = weights["coverage_thresholds"]
        assert thresholds["consumption_ppp_minimum_percent"] == 85.0
        assert thresholds["gdp_ppp_minimum_percent"] == 85.0
        assert thresholds["population_minimum_percent"] == 80.0

    def test_usa_country_profile_loads(self):
        profile = load_country_profile("USA")
        assert profile["country"] == "USA"
        assert profile["essential_basket"]["categories"]["food"] == 0.24
        weights = profile["essential_basket"]["categories"].values()
        assert sum(weights) == pytest.approx(1.0)

    def test_ea_country_profile_loads(self):
        profile = load_country_profile("EA")
        assert profile["country"] == "EA"
        assert profile["money"]["preferred_aggregate"] == "M3"

    def test_tha_country_profile_loads(self):
        profile = load_country_profile("THA")
        assert profile["country"] == "THA"

    def test_lowercase_geography_resolves(self):
        profile = load_country_profile("usa")
        assert profile["country"] == "USA"

    def test_unknown_country_raises_config_error(self):
        with pytest.raises(ConfigError):
            load_country_profile("ZZZ")

    def test_available_country_profiles_lists_all(self):
        assert set(available_country_profiles()) >= {"USA", "EA", "THA"}

    def test_all_essential_basket_weights_sum_to_one(self):
        for geo in ("USA", "EA", "THA"):
            profile = load_country_profile(geo)
            weights = profile["essential_basket"]["categories"].values()
            assert sum(weights) == pytest.approx(1.0), geo

    def test_all_producer_import_weights_sum_to_one(self):
        for geo in ("USA", "EA", "THA"):
            profile = load_country_profile(geo)
            weights = profile["producer_import"]["component_weights"].values()
            assert sum(weights) == pytest.approx(1.0), geo

    def test_all_housing_pressure_score_weights_sum_to_one(self):
        for geo in ("USA", "EA", "THA"):
            profile = load_country_profile(geo)
            weights = profile["housing"]["pressure_score_weights"].values()
            assert sum(weights) == pytest.approx(1.0), geo

    def test_synchronization_composite_weights_sum_to_one(self):
        weights = load_global_weights()["synchronization"]["composite_weights"]
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_producer_pressure_composite_weights_sum_to_one(self):
        weights = load_global_weights()["producer_pressure"]["composite_weights"]
        assert sum(weights.values()) == pytest.approx(1.0)
