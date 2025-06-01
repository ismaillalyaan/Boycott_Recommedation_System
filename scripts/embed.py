import mysql.connector
from mysql.connector import Error
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Database configuration
db_config = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "122005",
    "database": "recsys"
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        logging.info("Successfully connected to the database.")
        return conn
    except Error as e:
        logging.error(f"Error connecting to database: {e}")
        raise

def main():
    try:
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Clear previous embeddings and clusters
        logging.info("Clearing previous embeddings and clusters...")
        cursor.execute("DELETE FROM product_embeddings")
        cursor.execute("DELETE FROM product_clusters")
        conn.commit()

        # Fetch products
        logging.info("Fetching products from the database...")
        cursor.execute("SELECT product_id, name, description, category FROM products")
        products = cursor.fetchall()

        if not products:
            logging.error("No products found in the database.")
            raise ValueError("Products table is empty.")

        # Generate text for embeddings
        texts = [f"{row['name']} {row['description'] if row['description'] else ''} {row['category'] if row['category'] else ''}" for row in products]
        product_ids = [row['product_id'] for row in products]
        logging.info(f"Fetched {len(product_ids)} products.")

        # Generate embeddings
        logging.info("Generating embeddings with Alibaba-NLP/gte-large-en-v1.5...")
        model = SentenceTransformer("all-MiniLM-L6-v2", trust_remote_code=True)
        embeddings = model.encode(texts, convert_to_tensor=False)

        # Perform K-Means clustering
        num_clusters = min(10, len(products))  # Use 10 clusters or fewer if dataset is small
        logging.info(f"Clustering products into {num_clusters} clusters...")
        kmeans = KMeans(n_clusters=num_clusters, random_state=42)
        cluster_labels = kmeans.fit_predict(embeddings)

        # Insert embeddings
        logging.info("Inserting embeddings into product_embeddings table...")
        for pid, emb in zip(product_ids, embeddings):
            emb_json = json.dumps(emb.tolist())  # Store as JSON
            cursor.execute("""
                INSERT INTO product_embeddings (product_id, embedding)
                VALUES (%s, %s)
            """, (pid, emb_json))

        # Insert cluster assignments, converting NumPy int32 to Python int
        logging.info("Inserting cluster assignments into product_clusters table...")
        for pid, cluster_id in zip(product_ids, cluster_labels):
            cursor.execute("""
                INSERT INTO product_clusters (product_id, cluster_id)
                VALUES (%s, %s)
            """, (pid, int(cluster_id)))  # Convert NumPy int32 to Python int

        conn.commit()
        logging.info(f"Successfully inserted {len(product_ids)} embeddings and cluster assignments.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
        logging.info("Database connection closed.")

if __name__ == "__main__":
    main()