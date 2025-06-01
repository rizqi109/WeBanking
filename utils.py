def format_rupiah(amount):
    """Mengubah angka menjadi format Rupiah (contoh: 1000000.0 -> 1.000.000,00)"""
    amount = float(amount)
    amount_str = "{:.2f}".format(amount)
    amount_str = amount_str.replace('.', ',')
    integer_part, decimal_part = amount_str.split(',')
    integer_part = integer_part[::-1]
    chunks = [integer_part[i:i+3] for i in range(0, len(integer_part), 3)]
    integer_part = '.'.join(chunks)[::-1]
    return f"{integer_part},{decimal_part}"