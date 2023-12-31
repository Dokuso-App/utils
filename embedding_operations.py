import torch
import numpy as np
import torch.nn.functional as F
from scipy.stats import percentileofscore
from .clip_processing import compute_text_embeddings as clip
from .fclip_processing import compute_text_embeddings as fclip
from .clip_multilingual_processing import compute_text_embeddings as mclip


device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def get_similarity(image_features, text_features):
    '''
    Compute the cosine similarity between the image and text features.

    Args:
        image_features (torch.Tensor): Image features of shape (1, 512)
        text_features (torch.Tensor): Text features of shape (1, 512)
    Returns:
        similarity (torch.Tensor): Cosine similarity of shape (1, 1)
    '''
    image_features_normalized = F.normalize(image_features, dim=1)
    text_features_normalized = F.normalize(text_features, dim=1)
    similarity = text_features_normalized @ image_features_normalized.T
    return similarity


def add_embeddings_to_taxonomy(taxonomy, model='clip', path=[]):
    """
    This recursive function will add an 'embedding' key to every node in the taxonomy.

    Args:
        taxonomy (dict): The taxonomy dictionary
        model (str): The name of the model to use for computing the embeddings
        path (list): The path to the current node
    """
    if model not in ['clip', 'fclip', 'mclip']:
        raise ValueError('Expecting one of the following models: clip, fcip')
    for key, value in taxonomy.items():
        # Create the text phrase for the current path + new key
        # phrase = ' '.join(path + [key])
        phrase = key
        if key!='embedding':
            # Assign the embedding for the current node
            taxonomy[key]['embedding'] = eval(model)(phrase)
            if isinstance(value, dict) and value:  
                # If there's a nested dictionary, recurse into it
                add_embeddings_to_taxonomy(taxonomy[key], model, path + [key])


def add_embedding_to_leaves(data_dict, model="clip", current_path=""):
    """
    This recursive function will add an 'embedding' key to every leaf node with the path as its value.
    
    Args:
        data_dict (dict): The dictionary to add embeddings to
        model (str): The name of the model to use for computing the embeddings
        current_path (str): The current path to the node
    
    Returns:
        new_dict (dict): The dictionary with the embeddings added
    """
    # This recursive function will add an 'embedding' key to every leaf node with the path as its value.
    if not data_dict:  # If the dictionary is empty, we're at a leaf node.
        # Return a new dictionary with the embedding key, the value is the current path without the leading "->".
        text = f"a photo of a {current_path.lower()}".strip()
        return {'embedding': eval(model)(text)}  
    
    new_dict = {}  # This will hold the new dictionary with embeddings.
    for key, value in data_dict.items():
        # For each key in the dictionary, we build the path by appending the key to the current path.
        # Then we call the function recursively with the new path and the value (which is a dictionary itself).
        text = f"{key} {current_path}"
        new_dict[key] = add_embedding_to_leaves(value, model, text)
    
    return new_dict  # Return the new dictionary with all embeddings added.



def find_best_match_at_level(embeddings, image_embedding):
    """
    This function will find the best match at the current level of the taxonomy.
    
    Args:
        embeddings (dict): The embeddings dictionary
        image_embedding (torch.Tensor): The image embedding tensor
        
    Returns:
        best_match (str): The best match at the current level
        highest_similarity (float): The highest similarity score at the current level
    """
    highest_similarity = -1
    best_match = None
    for key, value in embeddings.items():
        if isinstance(value, dict) and 'embedding' in value:
            similarity = get_similarity(image_embedding, value['embedding'].to(device).reshape(1, -1))
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = key
    return best_match, highest_similarity

def find_best_matches(image_embedding, precomputed_embeddings, path=[]):
    """
    This recursive function will find the best matches for the image embedding at each level of the taxonomy.

    Args:
        image_embedding (torch.Tensor): The image embedding tensor
        precomputed_embeddings (dict): The precomputed embeddings dictionary
        path (list): The current path to the node
    
    Returns:
        path (list): The path to the best match
    """
    current_level = precomputed_embeddings
    for key in path:
        current_level = current_level[key]

    best_match, _ = find_best_match_at_level(current_level, image_embedding)
    
    if best_match is not None:
        new_path = path + [best_match]
        # Check if there are more levels below
        if 'embedding' in current_level[best_match] and isinstance(current_level[best_match], dict):
            # Continue searching deeper
            return find_best_matches(image_embedding, precomputed_embeddings, new_path)
        else:
            # If no deeper level, return the current path
            return new_path

    return path  # If no best match is found, return the current path

def find_most_similar_path(input_tensor, data_dict):
    """
    This function will find the most similar path in the taxonomy for the input tensor.

    Args:
        input_tensor (torch.Tensor): The input tensor
        data_dict (dict): The taxonomy dictionary
    
    Returns:
        result (list): The most similar path
    """
    # Helper function to recursively search the dictionary and compute cosine similarity
    def search_dict_for_similarity(sub_dict, input_tensor, current_path="", max_similarity={'score': -1, 'path': ''}):
        """
        This recursive function will search the dictionary for the most similar path to the input tensor.
        
        Args:
            sub_dict (dict): The current dictionary
            input_tensor (torch.Tensor): The input tensor
            current_path (str): The current path to the node
            max_similarity (dict): The current maximum similarity score and path
        
        Returns:
            max_similarity (dict): The maximum similarity score and path
        """
        for key, value in sub_dict.items():
            # If we find an embedding, compute the cosine similarity
            new_path = f"{current_path} -> {key}" if current_path else key
            if 'embedding' in value:
                similarity = get_similarity(input_tensor,  value['embedding'].to(device))
                if similarity > max_similarity['score']:
                    max_similarity['score'] = similarity
                    max_similarity['path'] = new_path
            else:
                # Otherwise, continue searching down the dictionary
                search_dict_for_similarity(value, input_tensor, new_path, max_similarity)
        return max_similarity

    # Start the search from the root of the dictionary
    result = search_dict_for_similarity(data_dict, input_tensor)
    # Return the path with the highest cosine similarity score
    return result['path'].split(' -> ')

def find_similar_paths(input_tensor, data_dict, threshold):
    """
    This function will find the paths in the taxonomy that are similar to the input tensor.

    Args:
        input_tensor (torch.Tensor): The input tensor
        data_dict (dict): The taxonomy dictionary
        threshold (float): The threshold for the similarity score
    
    Returns:
        result_paths (list): The paths that are similar to the input tensor
    """
    # Helper function to recursively search the dictionary and compute cosine similarity
    def search_dict_for_similarity(sub_dict, input_tensor, current_path="", similar_paths=[]):
        """
        This recursive function will search the dictionary for the most similar path to the input tensor.
        
        Args:
            sub_dict (dict): The current dictionary
            input_tensor (torch.Tensor): The input tensor
            current_path (str): The current path to the node
            similar_paths (list): The list of similar paths
        
        Returns:
            similar_paths (list): The list of similar paths
        """
        for key, value in sub_dict.items():
            # If we find an embedding, compute the cosine similarity
            new_path = f"{current_path} -> {key}" if current_path else key
            if 'embedding' in value:
                similarity = get_similarity(input_tensor, value['embedding'].to(device)).cpu()
                similar_paths.append((new_path, similarity))
            else:
                # Otherwise, continue searching down the dictionary
                search_dict_for_similarity(value, input_tensor, new_path, similar_paths)

    # Collect similarity values for all leaf nodes
    similar_paths = []
    search_dict_for_similarity(data_dict, input_tensor, similar_paths=similar_paths)

    # Extract similarity values
    similarities = [similarity.numpy()[0][0] for _, similarity in similar_paths]

    # Calculate the percentile rank for each leaf node's similarity
    percentile_ranks = [percentileofscore(similarities, similarity, kind='weak') for similarity in similarities]

    # Filter and return paths where the product of similarity and percentile rank is above the threshold
    result_paths = []
    for (path, similarity), rank in zip(similar_paths, percentile_ranks):
        if similarity * rank / 100.0 >= threshold:
            result_paths.append({'value': path, 'similarity': similarity, 'rank': rank})

    return result_paths






