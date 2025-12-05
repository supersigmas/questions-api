

import json

f = open("questions.json", "r")
data = json.load(f)

data = data["data"]

ls = set()

ls = {i['category'] for i in data}

d = {i: 0 for i in ls}

difficulty = {i['difficulty'] for i in data}

difficulty_d = {i: 0 for i in difficulty}

for i in ls:
    for j in data:
        if j['category'] == i:
            d[i] += 1

for i in difficulty:
    for j in data:
        if j['difficulty'] == i:
            difficulty_d[i] += 1




# print("Easy:", easy)
print(difficulty_d)
print(ls)
print(d)
#
# f = open("questions_2.json", "r")
# data = json.load(f)
#
# data = data["data"]
#
# ls = set()
#
# ls = {i['category'] for i in data}
#
# d = {i: 0 for i in ls}
#
# for i in ls:
#     for j in data:
#         if j['category'] == i:
#             d[i] += 1
#
#
# print(ls)
# print(d)

from collections import defaultdict

with open("questions.json", "r") as f:
    data = json.load(f)["data"]

# category -> difficulty -> count
difficulties_by_category = defaultdict(lambda: defaultdict(int))

for item in data:
    diff = item.get("difficulty")
    cat = item.get("category")
    if diff and cat:
        difficulties_by_category[cat][diff] += 1

# convert to normal dicts
difficulties_by_category = {cat: dict(diffs) for cat, diffs in difficulties_by_category.items()}

print(difficulties_by_category)