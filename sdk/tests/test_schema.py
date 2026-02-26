# SPDX-License-Identifier: Apache-2.0
import pytest
from securecollab import schema

def test_schema_placeholder():
    with pytest.raises(NotImplementedError):
        schema.analyze_csv_columns("/nonexistent.csv")
