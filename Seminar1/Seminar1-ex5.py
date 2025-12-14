z=list(map(int, input().split()))
N=str(z[0])
b=z[1]
c=z[2]
l=[]
for i in range(len(N)):
    l.append(int(N[i]))
w=[]
l=l[::-1]
for i in range(len(l)):
    q=l[i]*b**i
    w.append(q)
p=sum(w)
listochek=[]
while p>0:
    celoe=p%c
    p=p//c
    listochek.append(celoe)
listochek.reverse()
if listochek:
    print(''.join(map(str, listochek)))
else:
    print(0)