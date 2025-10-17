N= int(input())
l = list(map(int, input().split()))
k = N // 2  
for i in l:
    count = 0
    for z in l:
        if z < i:
            count += 1
    if count == k:
        print(i)
        break