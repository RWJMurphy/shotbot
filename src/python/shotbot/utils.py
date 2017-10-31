import string


def seq_encode(number, symbols):
    d, m = divmod(number, len(symbols))
    if d > 0:
        return seq_encode(d, symbols) + symbols[m]
    return symbols[m]


BASE36_CHARS = string.digits + string.ascii_lowercase


def base36_encode(number):
    return seq_encode(number, BASE36_CHARS)


def base36_decode(str):
    return int(str, base=36)
