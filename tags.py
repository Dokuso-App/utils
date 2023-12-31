import pandas as pd
import torch

from .text_processing import build_text
from .clip_processing import compute_text_embeddings as clip_text
from .fclip_processing import compute_text_embeddings as fclip_text
from .clip_multilingual_processing import compute_text_embeddings as mclip_text

from .clip_processing import compute_image_embeddings as clip_image
from .fclip_processing import compute_image_embeddings as fclip_image
from .clip_multilingual_processing import compute_image_embeddings as mclip_image
from .embedding_operations import find_best_matches, find_most_similar_path, find_similar_paths
from .taxonomies import (taxonomy_db_clip, attributes_fclip_text, attributes_clip_text, 
                        attributes_fclip, taxonomy_fclip, attributes_clip, taxonomy_clip)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def compute_item_embeddings(item_data, text_cols, text_cols_full, cookies_dict):
    """
    Compute the embeddings for a given item.
    
    Args:
        item_data (dict): The item data
        text_cols (list): The columns to use for the text embeddings
        text_cols_full (list): The columns to use for the text embeddings
        cookies_dict (dict): The cookies to use for the request
    
    Returns:
        embeddings (tuple): The image and text embeddings
    """
    
    img_url = item_data['Product image URL']
    shop_link = item_data['Product page URL']
    
    text = build_text(item_data, text_cols)
    text_full = build_text(item_data, text_cols_full)

    # Image embeddings
    image_embedding_clip = clip_image(img_url, cookies_dict)
    if image_embedding_clip is not None:
        image_embedding_clip = image_embedding_clip.to(device)
        
    image_embedding_fclip = fclip_image(img_url, cookies_dict)
    if image_embedding_fclip is not None:
        image_embedding_fclip = image_embedding_fclip.to(device)

    # Text embeddings
    text_embedding_fclip = fclip_text(text).to(device)
    if text_embedding_fclip is not None:
        text_embedding_fclip = text_embedding_fclip.to(device)
        
    text_full_embedding_clip = clip_text(text_full).to(device)
    if text_full_embedding_clip is not None:
        text_full_embedding_clip = text_full_embedding_clip.to(device)

    return (image_embedding_clip,
            image_embedding_fclip,
            text_embedding_fclip,
            text_full_embedding_clip)

def predict_tags(embeddings, threshold=0.25):
    """
    Predict the tags for a given item.
    
    Args:
        embeddings (tuple): The image and text embeddings
        threshold (float): The threshold for the similarity score
    
    Returns:
        categories (list): The categories
        attributes (list): The attributes
    """

    # Get the embeddings
    (image_embedding_clip,
    image_embedding_fclip,
    text_embedding_fclip,
    text_full_embedding_clip) = embeddings

    categories, attributes = None, None
    
    if not (image_embedding_clip is None or text_full_embedding_clip is None):
        
        blend_full_embedding_clip = torch.concat([image_embedding_clip, text_full_embedding_clip]).mean(0).reshape(1, -1)
        
        categories = find_best_matches(blend_full_embedding_clip, taxonomy_db_clip)

    if not (image_embedding_fclip is None or text_embedding_fclip is None):
        
        blend_embedding_fclip = torch.concat([image_embedding_fclip, text_embedding_fclip]).mean(0).reshape(1, -1)
        
    
        attributes = []
        for attr in attributes_clip:
      
            best_path = find_similar_paths(blend_embedding_fclip, attributes_fclip_text[attr], threshold)
    
            # attributes[attr] = ', '.join(best_path).strip()
            attributes.append({'attr': attr, 'similarities': best_path})

    return categories, attributes
    
    
def get_image_top_tags(img_url, THRESHOLD=0.25):
    """
    Get the top tags for a given image.
    
    Args:
        img_url (str): The URL of the image
        THRESHOLD (float): The threshold for the similarity score
    
    Returns:
        tags_by_category (dict): The tags by category
    """

    col_name = f'similarity_{col_idx}'
    top_tags_df[col_name] = pd.Series(tags_similarities_dict[img_url])
    top_tags_df = top_tags_df[top_tags_df[col_name]>0.2]
    p = top_tags_df.groupby('category')[col_name].rank(pct=True)
    p.name = f'percentile_{col_idx}'
    top_tags_df = top_tags_df.join(p)
    top_tags_df[f'score_{col_idx}'] = top_tags_df[col_name] * top_tags_df[p.name]
    
    # Filter and sort based on score
    filtered_df = top_tags_df[top_tags_df[f'score_{col_idx}'] > THRESHOLD].sort_values(by=f'score_{col_idx}', ascending=False)
    
    # Create a dictionary of top tags for each category and each similarity column
    tags_by_category = filtered_df.groupby('category')['value'].agg(set).map(lambda x: list(x))
    tags_by_category = tags_by_category.to_dict()

    return tags_by_category


def get_image_tags_similarity(img_url, tags_embeddings):
    """
    Get the similarity scores for the tags of a given image.
    
    Args:
        img_url (str): The URL of the image
        tags_embeddings (dict): The tags embeddings
    
    Returns:
        results (dict): The similarity scores for the tags
    """
    results = {}
    # Compute the similarity scores for each category
    for category in tags_embeddings:
        tag_similarities = []
        for tag in tags_embeddings[category]:
            score = get_similarity(e_img_fclip[img_url], tags_embeddings[category][tag].reshape(1,-1)).item()
            if score is not None:
                tag_similarities.append(score)

        if tag_similarities:
            tag_similarity_df = pd.DataFrame({'similarity': tag_similarities}, tags_embeddings[category])
            results[category] = tag_similarity_df.T.to_dict()
    return results
            
