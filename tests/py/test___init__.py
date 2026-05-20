#R001: Python test lane coverage for package marker docstring.
#R001-T01: Python test lane exists for package docstring requirement.

import matchy


def test_matchy_package_exposes_non_empty_module_docstring() -> None:
    #R001: Package marker docstring is present for module introspection.
    assert bool((matchy.__doc__ or "").strip())
