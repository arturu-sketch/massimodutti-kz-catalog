#!/usr/bin/env python3
import json

with open('/root/workspace/md-parser/clone/products.json') as f:
    products = json.load(f)

cats = {}
for p in products:
    s = p.get('section', '').strip()
    f = p.get('family', '').strip()
    if not f or not s: continue
    if s not in cats: cats[s] = {}
    cats[s][f] = cats[s].get(f, 0) + 1

with open('/root/workspace/md-parser/clone/categories.json', 'w') as f:
    json.dump(cats, f, ensure_ascii=False)

print('Products:', len(products))
print('Categories total:', sum(len(v) for v in cats.values()))
print('Sections:', list(cats.keys()))
with_img = sum(1 for p in products if p.get('images'))
print('With images:', with_img)
if products:
    print('Sample images:', products[0].get('images', [])[:2])
