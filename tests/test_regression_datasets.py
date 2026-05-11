from lummevia_datasets import get_dataset


def test_pm_dataset_fixture_is_valid() -> None:
    dataset = get_dataset("pm_business_brief_dataset")

    assert dataset.dataset_id == "pm_business_brief_dataset"
    assert dataset.template_id == "pm_business_brief"
    assert dataset.version == "v1"
    assert len(dataset.cases) == 5
    assert all(case.template_id == dataset.template_id for case in dataset.cases)
    assert all(case.expected_keywords for case in dataset.cases)
    assert all(case.expected_sections for case in dataset.cases)
