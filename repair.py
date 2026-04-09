with open('app.py', 'rb') as f:
    text = f.read().decode('utf-8', errors='replace')

text = text.replace('?? Find Jobs', '🔍 Find Jobs')
text = text.replace('?? Application History', '📜 Application History')
text = text.replace('?? Refresh History', '🔄 Refresh History')
text = text.replace('??</div>', '📭</div>')
text = text.replace('?? {a.get("company", "Unknown Company")} &nbsp;\ufffd&nbsp; Applied:', '🏢 {a.get("company", "Unknown Company")} &nbsp;·&nbsp; Applied:')

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Repaired!")
