n,p=input().split()
n=int(n)
G=len(p)//n
p=list(p)
full=[]
kusochek=[]
while p!=[]:
    kusochek=p[0:G:]
    p=p[G::]
    z=kusochek[::-1]
    full.extend(z)
    kusochek=[]
print(''.join(full))