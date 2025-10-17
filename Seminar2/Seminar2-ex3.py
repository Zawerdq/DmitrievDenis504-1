s=input()
palendrome=s[::-1]==s
mirror_dict={
    'A': 'A',
    'Y': 'Y',
    'M': 'M',
    '1': '1',
    '8': '8',
    'H': 'H',
    'I': 'I',
    'O': 'O',
    'T': 'T',
    'U': 'U',
    'V': 'V',
    'W': 'W',
    'X': 'X',
    'E': '3',
    'J': 'L',
    'S': '2',
    'Z': '5',
    '3': 'E',
    'L': 'J',
    '2': 'S',
    '5': 'Z'
}
mirror_s=''
for character in s:
    if character not in mirror_dict.keys():
        break
    mirror_s += mirror_dict[character]
#map() - думайте
print(mirror_s)
mirrored = mirror_s[::-1]==s
if mirrored and palendrome:
    print(s+ ' is a mirrored palindrome')
elif mirrored:
    print(s+ 'is a mirrored string')
elif palendrome:
    print(s+ ' is a palindrome')
else:
    print(s+ ' is not a palindrome')