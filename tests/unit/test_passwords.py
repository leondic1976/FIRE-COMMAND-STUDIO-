import hashlib
from apps.api.auth import password_hash,password_valid


def test_versioned_scrypt_random_salts_and_corrupt_hashes():
    password='synthetic-test-password-only'
    first,second=password_hash(password),password_hash(password)
    assert first!=second and first.startswith('scrypt$16384$8$5$')
    assert password_valid(password,first)
    assert not password_valid('wrong',first)
    assert not password_valid(password,'scrypt$999999999$8$5$invalid$invalid')
    assert not password_valid(password,'malformed')


def test_legacy_hash_can_be_verified_for_migration():
    salt=bytes(16)
    key=hashlib.scrypt(b'legacy-synthetic',salt=salt,n=16384,r=8,p=1).hex()
    assert password_valid('legacy-synthetic',salt.hex()+':'+key)
