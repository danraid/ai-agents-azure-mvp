def modulo_10(num: str) -> int:
    soma, mult = 0, 2
    for d in reversed(num):
        p = int(d) * mult
        soma += p // 10 + p % 10
        mult = 1 if mult == 2 else 2
    resto = soma % 10
    return (10 - resto) % 10

def modulo_11(num: str) -> int:
    pesos = [2,3,4,5,6,7,8,9]
    soma, i = 0, 0
    for d in reversed(num):
        soma += int(d) * pesos[i]
        i = (i+1) % len(pesos)
    resto = soma % 11
    dv = 11 - resto
    return 0 if dv in (0,10,11) else dv
