import ollama

def get_embedding(text: str, model: str = "nomic-embed-text"):
    response = ollama.embeddings(
        model=model,
        prompt=text
    )
    return response["embedding"]


#TODO: write a function which writes the whole agent context into a json file