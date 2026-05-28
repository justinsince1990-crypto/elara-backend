conversations = {}
def get_history(conv_id):
    if conv_id not in conversations: conversations[conv_id] = []
    return conversations[conv_id]
