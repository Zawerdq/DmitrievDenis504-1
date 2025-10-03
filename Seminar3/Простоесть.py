n=int(input())
def func(n,k=2):
        if n<2:
                return[]
        if pow(k,2) > n:
                return[n]
        if n%k==0:
                return([k] + func(n//k,k))
        else:
                return func(n,k+1)
list1=func(n)
list2=list1
count=0
for i in range(1000):
        if i in list2:
                k=list2.count(i)
                while i in list2:
                    list2.remove(i)
                s=str(i)+'^'+str(k)+'*'
                s=list(s)
                list2.extend(s)
list2.pop()
print(''.join(list2))