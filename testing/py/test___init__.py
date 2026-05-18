#R001: Python test lane coverage for package docstring marker behavior.
#R001-T01: Python test lane exists for package docstring requirement.

import matchy


def test_matchy_docstring_is_non_empty() -> None:
    assert isinstance(matchy.__doc__, str)
    assert (matchy.__doc__ or '').strip() != ''
