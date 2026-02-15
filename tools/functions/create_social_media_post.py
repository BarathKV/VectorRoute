import requests

def create_social_media_post(username, text_content) -> str:
    """
    Create a social media post by sending a POST request to the endpoint.
    
    Args:
        username (str): The username of the poster
        text_content (str): The content of the post
        
    Returns:
        str: Response message from the server
    """
    url = "http://localhost:5000/social_media/post"
    
    payload = {
        "username": username,
        "text_content": text_content
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return f"Error creating post: {str(e)}"