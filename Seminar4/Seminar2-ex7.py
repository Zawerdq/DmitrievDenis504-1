l=list(map(int, input().split()))
count=0
for i in l:
    if l.count(i)>=l.count(count):
        count=i
print(count)