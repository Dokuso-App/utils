import pandas as pd
import torch

from .text_processing import build_text
from .clip_processing import compute_text_embeddings as clip_text
from .fclip_processing import compute_text_embeddings as fclip_text
from .clip_multilingual_processing import compute_text_embeddings as mclip_text

from .clip_processing import compute_image_embeddings as clip_image
from .fclip_processing import compute_image_embeddings as fclip_image
from .clip_multilingual_processing import compute_image_embeddings as mclip_image
from .embedding_operations import find_best_matches, find_most_similar_path
from .taxonomies import *

def predict_tags(item_data, cookies_dict, text_cols, text_cols_full):
    
    img_url = item_data['Product image URL']
    shop_link = item_data['Product page URL']
    
    
    text = build_text(item_data, text_cols)
    text_full = build_text(item_data, text_cols_full)
    
    image_embedding_clip = clip_image(img_url, cookies_dict)
    image_embedding_fclip = fclip_image(img_url, cookies_dict)
    
    text_embedding_fclip = fclip_text(text)
    
    text_full_embedding_clip = clip_text(text_full)
    
    blend_embedding_fclip = torch.concat([image_embedding_fclip, text_embedding_fclip]).mean(0).reshape(1, -1)
    
    blend_full_embedding_clip = torch.concat([image_embedding_clip, text_full_embedding_clip]).mean(0).reshape(1, -1)
    
    categories = find_best_matches(blend_full_embedding_clip, taxonomy_db_clip)

    attributes = {}
    for attr in attributes_clip:
  
        best_path = find_most_similar_path(blend_embedding_fclip, attributes_fclip_text[attr])

        attributes[attr] = ' '.join(best_path).strip()

    return categories, attributes
    
def get_image_top_tags(img_url, THRESHOLD=0.25):
    
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


# def get_image_top_tags(img_url, tags_embeddings):

#     top_tags = {}

#     results = get_image_tags_similarity(img_url, tags_embeddings)

#     for category in results:
#         for tag in results[category]:
#             d = results[category][tag]
#             d['category'] = category
#             top_tags[tag] = d

#     similarities = get_similarity(e_img_cat.cuda(), e_tags.cuda())

#     top_tags_df = tags_df.copy()
#     top_tags_df['similarity'] = pd.Series(similarities[:, 0].cpu())
#     p = top_tags_df.groupby('category')['similarity'].rank(pct=True)
#     p.name = 'percentil'
#     top_tags_df = top_tags_df.join(p)
#     # top_tags_df = top_tags_df.reset_index().rename(columns={'index': 'tag'})
#     top_tags_df['score'] = top_tags_df['similarity']*top_tags_df['percentil']
#     top_tags_df[top_tags_df['score']>0.2].sort_values(by='score', ascending=False)

#     top_tags_dict = top_tags_df[top_tags_df['score']>0.2].sort_values(by='score', ascending=False).groupby('category')['value'].agg(set).to_dict()
#     return top_tags_dict

def get_image_tags_similarity(img_url, tags_embeddings):

    results = {}

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
            