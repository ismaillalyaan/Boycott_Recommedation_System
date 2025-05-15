import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

boycott_df = pd.read_csv("cleaned_Boycott.csv")
non_boycott_df = pd.read_csv("cleaned_Non-Boycott.csv")

model = SentenceTransformer("all-MiniLM-L6-v2")

non_boycott_df['combined'] = non_boycott_df.apply(
    lambda row: str(row['category']) + ": " + str(row['description']) if pd.notna(row['category']) else str(row['description']),
    axis=1
)
non_boycott_combined = non_boycott_df['combined'].tolist()
non_boycott_embeddings = model.encode(non_boycott_combined, convert_to_numpy=True)

boycott_df['combined'] = boycott_df.apply(
    lambda row: str(row['category']) + ": " + str(row['description']) if pd.notna(row['category']) else str(row['description']),
    axis=1
)
boycott_combined = boycott_df['combined'].tolist()
boycott_embeddings = model.encode(boycott_combined, convert_to_numpy=True)

sim = cosine_similarity(boycott_embeddings, non_boycott_embeddings)

non_boycott_metadata = non_boycott_df[["product_name", "brand", "description"]].reset_index()

SIMILARITY_THRESHOLD = 0.45

results = []
for i in range(len(boycott_df)):
    sim_scores = sim[i]
    sorted_indices = np.argsort(sim_scores)[::-1]
    top_scores = sim_scores[sorted_indices]
    
    alternatives = []
    for idx, score in zip(sorted_indices[:2], top_scores[:2]):
        if score >= SIMILARITY_THRESHOLD:
            alternatives.append(non_boycott_metadata.iloc[idx]['product_name'])

    result = [boycott_df['product_name'][i]]
    result.extend(alternatives if alternatives else [None])  
    if len(result) < 3: 
        result.append(None)
    
    results.append(result[:3])  

results_df = pd.DataFrame(results, columns=['boycotted_product', 'alternative1', 'alternative2'])
results_df.to_csv('alternatives.csv', index=False)