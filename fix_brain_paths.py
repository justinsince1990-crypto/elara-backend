with open('/root/elara/brain.py', 'r') as f:
    code = f.read()

# Force brain.py to use the local filesystem for conversations, not objstore
patch = """
def load_conversation(conversation_id: str) -> dict:
    import os, json
    path = f"/root/elara/conversations/{conversation_id}.json"
    if not os.path.exists(path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="conversation_not_found")
    with open(path, "r") as f:
        return json.load(f)

def save_conversation(conv: dict) -> None:
    import os, json
    from datetime import datetime
    conv["updated_at"] = datetime.now().isoformat()
    path = f"/root/elara/conversations/{conv['id']}.json"
    os.makedirs("/root/elara/conversations", exist_ok=True)
    with open(path, "w") as f:
        json.dump(conv, f, indent=2)
"""

# Replace the old objstore functions
import re
code = re.sub(r'def load_conversation\(.*?return data', '', code, flags=re.DOTALL)
code = re.sub(r'def save_conversation\(.*?objstore\.save_blob\(key, conv\)', patch, code, flags=re.DOTALL)

with open('/root/elara/brain.py', 'w') as f:
    f.write(code)
