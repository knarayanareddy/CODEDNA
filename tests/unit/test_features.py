"""Unit tests for CodeDNA feature extraction."""
import pytest
from codedna.harvester.features import FeatureVector, extract_features, VECTOR_DIMS, compute_body_hash

class TestFeatureVector:
    def test_vector_has_correct_dimensions(self):
        vector = FeatureVector()
        assert len(vector.to_list()) == VECTOR_DIMS

    def test_vector_conversion_round_trip(self):
        original = FeatureVector(snake_case_ratio=0.8, single_char_var_rate=0.2, avg_function_length=15.0)
        data = original.to_list()
        restored = FeatureVector.from_list(data)
        assert restored.snake_case_ratio == original.snake_case_ratio

    def test_invalid_length_raises_error(self):
        with pytest.raises(ValueError):
            FeatureVector.from_list([0.5] * 16)

class TestFeatureExtraction:
    def test_extract_features_from_simple_function(self):
        source = 'def hello():\n    print("Hello, World!")'
        vector = extract_features(source)
        assert vector is not None
        assert len(vector.to_list()) == VECTOR_DIMS
        assert vector.decorator_rate == 0.0

    def test_extract_features_with_docstring(self):
        source = 'def documented_function():\n    """This is a docstring."""\n    pass'
        vector = extract_features(source)
        assert vector.avg_function_length >= 1

    def test_extract_features_with_comprehensions(self):
        source = "squares = [x**2 for x in range(10)]"
        vector = extract_features(source)
        assert vector.comprehension_rate > 0

    def test_extract_features_with_type_hints(self):
        source = "def add(a: int, b: int) -> int:\n    return a + b"
        vector = extract_features(source)
        assert vector.type_hint_rate > 0

    def test_extract_features_with_f_string(self):
        source = 'name = "World"\ngreeting = f"Hello, {name}!"'
        vector = extract_features(source)
        assert vector.fstring_rate > 0

    def test_extract_features_invalid_syntax_returns_empty_vector(self):
        source = "def unclosed("
        vector = extract_features(source)
        assert vector is not None
        assert len(vector.to_list()) == VECTOR_DIMS

class TestBodyHash:
    def test_compute_body_hash(self):
        content = "def hello():\n    pass"
        hash1 = compute_body_hash(content)
        assert len(hash1) == 64

    def test_compute_body_hash_deterministic(self):
        content = "def hello():\n    pass"
        hash1 = compute_body_hash(content)
        hash2 = compute_body_hash(content)
        assert hash1 == hash2

    def test_compute_body_hash_different_content(self):
        hash1 = compute_body_hash("def hello():\n    pass")
        hash2 = compute_body_hash("def goodbye():\n    pass")
        assert hash1 != hash2

class TestPrivacyConstraints:
    def test_no_source_code_in_vector(self):
        source = 'def secret_function():\n    password = "hunter2"\n    return password'
        vector = extract_features(source)
        # Verify vector is just numeric values (no source code strings)
        values = vector.to_list()
        assert len(values) == VECTOR_DIMS
        # Check that values are numeric (not strings containing source)
        numeric_values = [v for v in values if isinstance(v, (int, float))]
        assert len(numeric_values) == VECTOR_DIMS

    def test_body_hash_not_body(self):
        source = "def secret():\n    return 42"
        hash_value = compute_body_hash(source)
        assert "secret" not in hash_value
        assert len(hash_value) == 64
