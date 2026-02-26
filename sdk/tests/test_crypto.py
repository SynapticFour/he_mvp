# SPDX-License-Identifier: Apache-2.0
import pytest
from securecollab.exceptions import CryptoError

def test_crypto_placeholder():
    from securecollab import crypto
    with pytest.raises(NotImplementedError):
        crypto.generate_contexts()
