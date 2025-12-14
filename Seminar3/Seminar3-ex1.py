n, p = map(int, input().split())
a=n
b=p
while a != b:
    if a > b:
        a = a - b
    else:
        b = b - a
d = a
def Euclide(n, p):
    a0, b0 = n, p
    x0, y0 = 1, 0
    x1, y1 = 0, 1
    a, b = a0, b0
    while b != 0:
        q = a // b
        a, b = b, a % b
        x0, x1 = x1, x0 - q * x1
        y0, y1 = y1, y0 - q * y1
    return x0, y0

x, y = Euclide(n, p)
print(x, y, d)
