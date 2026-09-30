def test_engine_is_a_regular_package():
    import engine
    assert engine.__file__ is not None  # a namespace package (no __init__.py) has no __file__
