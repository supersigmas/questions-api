import json

f = open("questions.json", "r")
data = json.load(f)

data = data["data"]

extracted_q = {"data": []}

for q in data:
    if q['category'] == "literature":
        # add question to extracted_q
        extracted_q["data"].append(q)

print(extracted_q)
with open("extracted_questions.json", "w") as f:
    json.dump(extracted_q, f, indent=4)