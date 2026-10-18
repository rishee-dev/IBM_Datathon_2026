import re, os

filepath = r"c:\Users\mahar\OneDrive\Documents\IBM DataThon 2026\app\page.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Find all className attributes (both static and template strings)
classes = re.findall(r'className=(?:\{`([^`]+)`\}|["\']([^"\']+)["\'])', content)
flat_classes = []
for c1, c2 in classes:
    flat_classes.extend((c1 or c2).split())

effect_classes = set()
for c in flat_classes:
    if any(k in c.lower() for k in ["anim", "pulse", "spin", "glow", "radial", "gradient", "spark"]):
        effect_classes.add(c)

print("Effect classes found in page.tsx:")
for c in sorted(effect_classes):
    print(" -", c)
