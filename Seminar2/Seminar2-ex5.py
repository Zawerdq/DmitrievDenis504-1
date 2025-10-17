l=list(map(int, input().split()))
for i in range(len(l)-1, 0,-1): l[i], l[i-1]=l[i-1], l[i]
print(l)