# SPDX-License-Identifier: Apache-2.0
import pytest
from securecollab import SecureCollabClient

@pytest.fixture
def client():
    return SecureCollabClient("http://localhost:8000")
