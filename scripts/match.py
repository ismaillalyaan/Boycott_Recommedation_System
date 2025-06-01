import mysql.connector
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.corpus import wordnet
import nltk
import json

# Connect to database
conn = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="122005",
    database="recsys"
)
cursor = conn.cursor(dictionary=True)

# Clear previous similarity data
cursor.execute("DELETE FROM similarities")
conn.commit()

# Function to get synonyms for keyword enhancement
def get_synonyms(word):
    synonyms = set()
    for syn in wordnet.synsets(word):
        for lemma in syn.lemmas():
            synonyms.add(lemma.name().lower().replace('_', ' '))
    return synonyms

# Load product data including embeddings, clusters, and metadata
cursor.execute("""
    SELECT p.product_id, p.is_boycotted, e.embedding, p.name, p.description, p.category, c.cluster_id
    FROM products p
    JOIN product_embeddings e ON p.product_id = e.product_id
    JOIN product_clusters c ON p.product_id = c.product_id
""")
records = cursor.fetchall()

# Standardize categories and parse embeddings
for r in records:
    r['category'] = r['category'].strip().lower() if r['category'] else ""
    r['embedding'] = np.array(json.loads(r['embedding']), dtype=np.float32)

# Separate boycotted and non-boycotted products
boycott = [(r['product_id'], r['embedding'], r['name'], r['description'], r['category'], r['cluster_id']) 
           for r in records if r['is_boycotted']]
non_boycott = [(r['product_id'], r['embedding'], r['name'], r['description'], r['category'], r['cluster_id']) 
               for r in records if not r['is_boycotted']]

# Compute TF-IDF to find important keywords, including category
descriptions_with_category = [f"{r['description']} {r['category']}" if r['description'] else r['category'] for r in records]
vectorizer = TfidfVectorizer(stop_words='english', min_df=2)
tfidf_matrix = vectorizer.fit_transform(descriptions_with_category)
feature_names = vectorizer.get_feature_names_out()

# Ensure category-related keywords are included
target_keywords = {'spread', 'nut spread', 'butter', 'chocolate', 'snack'}
for kw in list(target_keywords):
    target_keywords.update(get_synonyms(kw))
max_tfidf = tfidf_matrix.max(axis=0).toarray()[0]
keywords = [feature_names[i] for i in range(len(max_tfidf)) if max_tfidf[i] > 0.2]
keywords = list(set(keywords) | target_keywords)

# Create binary keyword vectors
keyword_vectors = []
for desc, cat in zip([r['description'] for r in records], [r['category'] for r in records]):
    words = set(f"{desc} {cat}".lower().split()) if desc else set(cat.lower().split())
    vec = np.array([1 if any(kw in words for kw in get_synonyms(keyword) | {keyword}) else 0 for keyword in keywords])
    keyword_vectors.append(vec)

# Assign keyword vectors to boycott and non-boycott lists
boycott = [(bid, b_emb, b_name, b_desc, b_cat, b_cluster, keyword_vectors[i]) 
           for i, (bid, b_emb, b_name, b_desc, b_cat, b_cluster) in enumerate(boycott)]
non_boycott = [(nid, n_emb, n_name, n_desc, n_cat, n_cluster, keyword_vectors[i + len(boycott)]) 
               for i, (nid, n_emb, n_name, n_desc, n_cat, n_cluster) in enumerate(non_boycott)]

# Calculate similarities with clustering and flexible number of alternatives
ALPHA = 0.65  # Balanced weight for embedding similarity
SIMILARITY_THRESHOLD = 0.30 # Lowered to 45% for smoother matching
for bid, b_emb, b_name, b_desc, b_cat, b_cluster, b_kw_vec in boycott:
    alternatives = []
    
    # Prioritize products in the same cluster and category
    same_cluster_category_products = [(nid, n_emb, n_name, n_desc, n_cat, n_cluster, n_kw_vec) 
                                     for nid, n_emb, n_name, n_desc, n_cat, n_cluster, n_kw_vec in non_boycott 
                                     if n_cluster == b_cluster and n_cat == b_cat]
    
    # Fall back to same category if no matches in cluster
    if not same_cluster_category_products:
        same_cluster_category_products = [(nid, n_emb, n_name, n_desc, n_cat, n_cluster, n_kw_vec) 
                                         for nid, n_emb, n_name, n_desc, n_cat, n_cluster, n_kw_vec in non_boycott 
                                         if n_cat == b_cat]
    
    if not same_cluster_category_products:
        print(f"No non-boycotted products found in category '{b_cat}' for boycotted product ID {bid} (Name: {b_name}).")
        continue
    
    for nid, n_emb, n_name, n_desc, n_cat, n_cluster, n_kw_vec in same_cluster_category_products:
        # Compute cosine similarity
        cos_sim = cosine_similarity([b_emb], [n_emb])[0][0]
        # Compute Jaccard similarity for keywords
        intersection = np.sum(b_kw_vec & n_kw_vec)
        union = np.sum(b_kw_vec | n_kw_vec)
        jac_sim = intersection / union if union > 0 else 0
        # Compute combined similarity
        combined_sim = ALPHA * cos_sim + (1 - ALPHA) * jac_sim
        if combined_sim >= SIMILARITY_THRESHOLD:
            alternatives.append((nid, combined_sim, cos_sim, jac_sim, n_name, n_cat))
    
    # Sort alternatives by combined similarity descending
    alternatives.sort(key=lambda x: x[1], reverse=True)
    
    # Insert all alternatives that meet the threshold
    for nid, combined_sim, _, _, _, _ in alternatives:
        cursor.execute("""
            INSERT INTO similarities (boycott_id, alt_id, cosine_score)
            VALUES (%s, %s, %s)
        """, (bid, nid, float(combined_sim)))
    
    # Debug output
    print(f"Found {len(alternatives)} alternatives for boycotted product ID {bid} (Name: {b_name}, Category: {b_cat}, Cluster: {b_cluster})")
    for alt in alternatives:
        print(f"Alternative ID {alt[0]} (Name: {alt[4]}, Category: {alt[5]}): combined_sim={alt[1]:.3f}, cos_sim={alt[2]:.3f}, jac_sim={alt[3]:.3f}")

conn.commit()
cursor.close()
conn.close()
print("Updated similarities with BERT embeddings, clustering, 45% similarity threshold, and no limit on alternatives.")
