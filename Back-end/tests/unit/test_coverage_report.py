from app.models.coverage import CoverageReport


def test_included_count():
    report = CoverageReport(
        included_geographies=("USA", "EA", "THA"),
        missing_geographies=(),
    )
    assert report.included_count == 3


def test_default_missing_geographies_empty():
    report = CoverageReport(included_geographies=("USA",), missing_geographies=())
    assert report.missing_geographies == ()


def test_to_dict_includes_weight_disclosures():
    report = CoverageReport(
        included_geographies=("USA", "EA"),
        missing_geographies=("THA",),
        weights_renormalized=True,
        original_weights={"USA": 0.4, "EA": 0.3, "THA": 0.3},
        adjusted_weights={"USA": 0.571, "EA": 0.429},
    )
    d = report.to_dict()
    assert d["original_weights"]["THA"] == 0.3
    assert "THA" not in d["adjusted_weights"]
