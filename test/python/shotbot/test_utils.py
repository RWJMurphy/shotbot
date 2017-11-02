import pytest

from shotbot.utils import base36_decode, base36_encode, seq_encode

BASE36_SAMPLES = {
    0: '0',
    9: '9',
    10: 'a',
    35: 'z',
    36: '10',
    999999999: 'gjdgxr'
}


@pytest.mark.parametrize('number,encoded', BASE36_SAMPLES.items())
def test_base36_decode(encoded, number):
    assert base36_decode(encoded) == number


@pytest.mark.parametrize('number,encoded', BASE36_SAMPLES.items())
def test_base36_encode(encoded, number):
    assert base36_encode(number) == encoded


@pytest.mark.parametrize('sequence, format_char', [
    ('01', 'b'),
    ('01234567', 'o'),
    ('0123456789abcdef', 'x'),
])
def test_seq_encode(sequence, format_char):
    for i in range(1000):
        assert seq_encode(i, sequence) == format(i, format_char)
