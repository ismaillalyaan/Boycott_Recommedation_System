import pandas as pd
import mysql.connector
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from mysql.connector import Error
import json

try:
    new_products_df = pd.read_csv("../data/products_addition.csv")
except FileNotFoundError as e:
    print(f"Error: products_addition.csv not found: {e}")
    exit(1)
except pd.errors.EmptyDataError:
    print("Error: products_addition.csv is empty.")
    exit(1)
except Exception as e:
    print(f"Error loading products_addition.csv: {e}")
    exit(1)

required_columns = ["product_name", "description", "category", "country", "brand", "is_boycott"]
missing_columns = [col for col in required_columns if col not in new_products_df.columns]
if missing_columns:
    print(f"Error: Missing required columns {missing_columns} in products_addition.csv")
    exit(1)

# Add new products to the database
try:
    conn = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="122005",
        database="recsys"
    )
    cursor = conn.cursor(dictionary=True)
except Error as e:
    print(f"Error connecting to database: {e}")
    exit(1)

new_product_ids = []
skipped_rows = 0
try:
    print("Inserting new products into the database...")
    for idx, row in new_products_df.iterrows():
        try:
            name = row["product_name"]
            if not isinstance(name, str) or not name.strip():
                print(f"Skipping row {idx}: Invalid product name: {name}")
                skipped_rows += 1
                continue

            description = row["description"]
            if not isinstance(description, str):
                description = ""

            category = row["category"]
            if not isinstance(category, str) or not category.strip():
                print(f"Skipping row {idx}: Invalid category: {category}")
                skipped_rows += 1
                continue

            country = row["country"]
            if not isinstance(country, str):
                country = "Unknown"

            brand = row["brand"]
            if not isinstance(brand, str) or not brand.strip():
                print(f"Skipping row {idx}: Invalid brand: {brand}")
                skipped_rows += 1
                continue

            is_boycott = row["is_boycott"]
            if not isinstance(is_boycott, bool):
                print(f"Skipping row {idx}: Invalid is_boycott value: {is_boycott}")
                skipped_rows += 1
                continue

            cursor.execute("""
                INSERT INTO products (name, description, category, country, brand, is_boycotted)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, description, category, country, brand, is_boycott))
            new_product_ids.append(cursor.lastrowid)

        except Error as e:
            print(f"Error inserting row {idx}: {e}")
            skipped_rows += 1
            continue

    conn.commit()
    print(f"Inserted {len(new_product_ids)} new products. Skipped {skipped_rows} rows.")

except Error as e:
    print(f"Database error: {e}")
    conn.rollback()
finally:
    cursor.close()
    conn.close()

# Generate embeddings and clusters for new products
if new_product_ids:
    try:
        conn = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="122005",
            database="recsys"
        )
        cursor = conn.cursor(dictionary=True)

        # Fetch all products for retraining clusters
        cursor.execute("""
            SELECT product_id, name, description, category
            FROM products
        """)
        all_products = cursor.fetchall()

        # Generate text for embeddings
        texts = [f"{row['name']} {row['description'] if row['description'] else ''} {row['category'] if row['category'] else ''}" for row in all_products]
        product_ids = [row['product_id'] for row in all_products]

        print("Generating embeddings for all products with Alibaba-NLP/gte-large-en-v1.5...")
        model = SentenceTransformer("Alibaba-NLP/gte-large-en-v1.5", trust_remote_code=True)
        embeddings = model.encode(texts, convert_to_tensor=False)

        # Perform K-Means clustering
        num_clusters = min(10, len(all_products))
        print(f"Clustering {len(all_products)} products into {num_clusters} clusters...")
        kmeans = KMeans(n_clusters=num_clusters, random_state=42)
        cluster_labels = kmeans.fit_predict(embeddings)

        # Clear existing embeddings and clusters
        cursor.execute("DELETE FROM product_embeddings")
        cursor.execute("DELETE FROM product_clusters")
        conn.commit()

        # Insert embeddings and clusters
        for pid, emb, cluster_id in zip(product_ids, embeddings, cluster_labels):
            emb_json = json.dumps(emb.tolist())
            cursor.execute("""
                INSERT INTO product_embeddings (product_id, embedding)
                VALUES (%s, %s)
            """, (pid, emb_json))
            cursor.execute("""
                INSERT INTO product_clusters (product_id, cluster_id)
                VALUES (%s, %s)
            """, (pid, cluster_id))

        conn.commit()
        print(f"Inserted embeddings and clusters for {len(product_ids)} products.")

    except Error as e:
        print(f"Error during embedding or clustering: {e}")
        conn.rollback()
    except Exception as e:
        print(f"Unexpected error during embedding or clustering: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

# Update similarities for new products
if new_product_ids:
    try:
        conn = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="122005",
            database="recsys"
        )
        cursor = conn.cursor(dictionary=True)
        print("Updating similarities for new products...")

        cursor.execute("""
            SELECT p.product_id, p.is_boycotted, e.embedding, p.name, p.category, c.cluster_id
            FROM products p
            JOIN product_embeddings e ON p.product_id = e.product_id
            JOIN product_clusters c ON p.product_id = c.product_id
        """)
        records = cursor.fetchall()

        # Standardize categories and parse embeddings
        for r in records:
            r['category'] = r['category'].strip().lower() if r['category'] else ""
            r['embedding'] = np.array(json.loads(r['embedding']), dtype=np.float32)

        boycott = [(r['product_id'], r['embedding'], r['name'], r['category'], r['cluster_id']) for r in records if r['is_boycotted']]
        non_boycott = [(r['product_id'], r['embedding'], r['name'], r['category'], r['cluster_id']) for r in records if not r['is_boycotted']]

        new_boycott = [(pid, emb, name, cat, cluster) for pid, emb, name, cat, cluster in boycott if pid in new_product_ids]
        existing_boycott = [(pid, emb, name, cat, cluster) for pid, emb, name, cat, cluster in boycott if pid not in new_product_ids]
        new_non_boycott = [(pid, emb, name, cat, cluster) for pid, emb, name, cat, cluster in non_boycott if pid in new_product_ids]

        SIMILARITY_THRESHOLD = 0.7

        # Update similarities for new boycotted products
        for bid, b_emb, b_name, b_cat, b_cluster in new_boycott:
            alternatives = []
            same_cluster_category_products = [(nid, n_emb, n_name, n_cat, n_cluster) 
                                             for nid, n_emb, n_name, n_cat, n_cluster in non_boycott 
                                             if n_cluster == b_cluster and n_cat == b_cat]
            
            if not same_cluster_category_products:
                same_cluster_category_products = [(nid, n_emb, n_name, n_cat, n_cluster) 
                                                 for nid, n_emb, n_name, n_cat, n_cluster in non_boycott 
                                                 if n_cat == b_cat]
            
            if not same_cluster_category_products:
                print(f"No non-boycotted products in category '{b_cat}' for new boycotted product ID {bid} (Name: {b_name}).")
                continue

            for nid, n_emb, n_name, n_cat, n_cluster in same_cluster_category_products:
                sim = cosine_similarity([b_emb], [n_emb])[0][0]
                if sim >= SIMILARITY_THRESHOLD:
                    alternatives.append((nid, sim))

            alternatives.sort(key=lambda x: x[1], reverse=True)

            for nid, score in alternatives:
                cursor.execute("""
                    INSERT INTO similarities (boycott_id, alt_id, cosine_score)
                    VALUES (%s, %s, %s)
                """, (bid, nid, score))

            print(f"Found {len(alternatives)} alternatives for new boycotted product ID {bid} (Name: {b_name}, Category: {b_cat}, Cluster: {b_cluster})")

        # Update similarities for existing boycotted products with new non-boycotted products
        for bid, b_emb, b_name, b_cat, b_cluster in existing_boycott:
            alternatives = []
            same_cluster_category_products = [(nid, n_emb, n_name, n_cat, n_cluster) 
                                             for nid, n_emb, n_name, n_cat, n_cluster in new_non_boycott 
                                             if n_cluster == b_cluster and n_cat == b_cat]
            
            if not same_cluster_category_products:
                same_cluster_category_products = [(nid, n_emb, n_name, n_cat, n_cluster) 
                                                 for nid, n_emb, n_name, n_cat, n_cluster in new_non_boycott 
                                                 if n_cat == b_cat]
            
            if not same_cluster_category_products:
                print(f"No new non-boycotted products in category '{b_cat}' for existing boycotted product ID {bid} (Name: {b_name}).")
                continue

            for nid, n_emb, n_name, n_cat, n_cluster in same_cluster_category_products:
                sim = cosine_similarity([b_emb], [n_emb])[0][0]
                if sim >= SIMILARITY_THRESHOLD:
                    alternatives.append((nid, sim))

            alternatives.sort(key=lambda x: x[1], reverse=True)

            for nid, score in alternatives:
                cursor.execute("""
                    INSERT INTO similarities (boycott_id, alt_id, cosine_score)
                    VALUES (%s, %s, %s)
                """, (bid, nid, score))

            print(f"Found {len(alternatives)} new alternatives for existing boycotted product ID {bid} (Name: {b_name}, Category: {b_cat}, Cluster: {b_cluster})")

        conn.commit()
        print("Updated similarities table with new products and clustering.")

    except Error as e:
        print(f"Error updating similarities: {e}")
        conn.rollback()
    except Exception as e:
        print(f"Unexpected error updating similarities: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
else:
    print("No new products to process for embeddings, clusters, or similarities.")