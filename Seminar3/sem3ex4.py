size=int(input())
symb=input()
if size%2==0:
    i=0
    while i < size//2:
            i+=1
            print(symb*i)
    while i>0:
        if i==0:
            break
        print(symb*i)
        i-=1
else:
    i=0
    while i < (size//2+1):
        i+=1
        print(symb*i)
    while i>0:
        i-=1
        if i==0:
            break
        print(symb*i)
