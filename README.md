**RECSYS - A Product Recommendation System for Boycott Alternatives** 🚫🌟

I’m excited to share my latest project, RECSYS—a recommendation system designed to identify boycotted products and suggest ethical alternatives using machine learning and natural language processing. Below is an overview of the system architecture and how it works. Let me know your thoughts! 👇

---

🚀 **Live Demo**: 

---

### 📋 Project Overview
RECSYS is a web-based application that helps users identify whether a product is boycotted and suggests non-boycotted alternatives. It combines a Flask backend, a MySQL database, and a frontend built with HTML, CSS, and JavaScript. The system leverages machine learning for product detection (via YOLO) and embeddings (via Sentence Transformers) to recommend alternatives based on similarity.

---

### 📋 System Architecture
```
RECSYS
├── pycache
├── app
│   ├── about.html
│   ├── contact.html
│   ├── index.html
│   ├── request.html
│   ├── script.js
│   ├── styles.css
│   └── why-boycott.html
├── backend
│   ├── app.py
│   └── requirements.txt
├── data
│   ├── preprocess.py
│   ├── products_addition.csv
│   └── products.csv
├── models
│   └── best.pt
├── scripts
│   ├── embed.py
│   ├── match.py
│   ├── setup.py
│   └── update_products.py
└── System.txt
```
---

### 🛠️ How It Works

#### 1️⃣ Database Setup and Initialization (`setup.py`)
- **Purpose**: Sets up the MySQL database and populates it with product data.
- **Process**:
  - Drops and recreates tables: `products`, `product_embeddings`, `product_clusters`, and `similarities`.
  - Loads product data from `products.csv` (located in `data/`) using pandas.
  - Inserts product details (name, description, category, is_boycotted, country, brand) into the `products` table.
  - Implements constraints to ensure `boycott_id` references boycotted products and `alt_id` references non-boycotted ones in the `similarities` table.
- **Key File**: `setup.py`

---

#### 2️⃣ Product Embedding and Clustering (`embed.py`)
- **Purpose**: Generates embeddings for products and clusters them for better matching.
- **Process**:
  - Connects to the MySQL database and clears previous embeddings/clusters.
  - Fetches product data (name, description, category) from the `products` table.
  - Uses the `all-MiniLM-L6-v2` Sentence Transformer model to generate embeddings for product text.
  - Applies K-Means clustering (up to 10 clusters) to group similar products.
  - Stores embeddings and cluster assignments in `product_embeddings` and `product_clusters` tables.
- **Key File**: `embed.py`

---

#### 3️⃣ Matching Boycotted Products with Alternatives (`match.py`)
- **Purpose**: Finds non-boycotted alternatives for boycotted products.
- **Process**:
  - Fetches products, embeddings, and clusters from the database.
  - Separates products into boycotted and non-boycotted lists.
  - Uses TF-IDF to extract keywords and enhances them with synonyms (via NLTK’s WordNet).
  - Computes similarity using a combination of cosine similarity (on embeddings) and Jaccard similarity (on keywords).
  - Prioritizes alternatives in the same cluster and category, falling back to category-only matches.
  - Stores similarity scores in the `similarities` table for later retrieval.
- **Key File**: `match.py`

---

#### 4️⃣ Backend API and Image Processing (`app.py`)
- **Purpose**: Provides API endpoints for the frontend to process images, add products, and search products.
- **Process**:
  - Uses Flask to create a REST API with CORS support.
  - **Image Processing (`/process_image`)**: Uses YOLO (`best.pt` model) to detect products in uploaded images, queries the database to check if the product is boycotted, and retrieves alternatives if applicable.
  - **Product Search (`/search_products`)**: Supports autocomplete search by querying the database for product names matching the user’s input.
  - **Add Product (`/add_product`)**: Allows adding new products to the database (future integration with Microsoft Graph for Excel updates).
  - Returns JSON responses with product details, boycott status, and alternatives.
- **Key File**: `app.py`

---

#### 5️⃣ Frontend Interface (`index.html`, `script.js`, `styles.css`)
- **Purpose**: Provides a user-friendly interface to interact with the system.
- **Process**:
  - **UI (`index.html`)**: Offers two modes—image upload or text search—to identify products. Displays results and alternatives.
  - **Interactivity (`script.js`)**: Handles image uploads, previews, and API calls to `/process_image` and `/search_products`. Implements autocomplete for search and animates navigation with a red arrow effect.
  - **Styling (`styles.css`)**: Uses the Cairo font for Arabic text, applies RTL styling, and includes responsive design with animations for a polished look.
- **Key Files**: `index.html`, `script.js`, `styles.css`

---

### 🌟 Key Features
- **Image Recognition**: Detects products in images using YOLO.
- **NLP-Powered Matching**: Uses Sentence Transformers and TF-IDF for semantic and keyword-based similarity.
- **Clustering**: Groups similar products with K-Means for efficient matching.
- **Responsive Design**: RTL support with Arabic text and mobile-friendly layout.
- **Ethical Focus**: Helps users make informed choices by identifying boycotted products and suggesting alternatives.

---

### 🛠️ Technologies Used
- **Backend**: Flask, MySQL, YOLO (Ultralytics), Sentence Transformers, NLTK, scikit-learn
- **Frontend**: HTML, CSS, JavaScript
- **Data**: pandas, CSV files
- **Others**: Microsoft Graph (for future Excel integration)

---

### 📈 Future Improvements
- Integrate Microsoft Graph to update product data in Excel.
- Enhance image recognition accuracy with a larger YOLO dataset.
- Add user authentication and product submission moderation.
- Improve matching with more advanced NLP models.

---

I’d love to hear your feedback or collaborate on enhancing this project! Let’s connect. 💬 #MachineLearning #NLP #WebDevelopment #EthicalTech
