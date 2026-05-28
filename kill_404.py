import re

with open('brain.py', 'r') as f:
    text = f.read()

# Find the 404 line and replace it with auto-initialization, keeping exact spaces
new_text = re.sub(
    r'([ \t]+)raise HTTPException\(status_code=404, detail="Conversation not found"\)',
    r'\1conversations[req.conversation_id] = []\n\1logger.info("Auto-healed missing session.")', 
    text
)

with open('brain.py', 'w') as f:
    f.write(new_text)
print("\n✅ 404 successfully assassinated.\n")
